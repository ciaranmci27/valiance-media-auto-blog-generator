#!/usr/bin/env python3
"""
Autonomous Blog Generator

This script uses Claude to autonomously generate blog posts.
It can operate in several modes:
1. Manual mode: Generate a post about a specific topic
2. Autonomous mode: Process posts from a queue of blog ideas
3. Backfill images: Generate images for posts missing them
4. Backfill links: Add internal links to posts with fewer than recommended
5. Cleanup/refresh images: Remove bad images or replace them with new ones

Usage:
    python generator.py "topic to write about"          # Manual mode
    python generator.py --autonomous                    # Process ideas from queue
    python generator.py --autonomous --count 5          # Process up to 5 ideas
    python generator.py --backfill-images --count 10    # Backfill up to 10 images
    python generator.py --backfill-images-all           # Backfill ALL images
    python generator.py --backfill-links --count 5      # Backfill up to 5 posts
    python generator.py --backfill-links-all            # Backfill ALL links
    python generator.py --cleanup-image post-slug       # Remove image by slug
    python generator.py --cleanup-image-id post-uuid    # Remove image by post ID
    python generator.py --refresh-image post-slug       # Replace image by slug
    python generator.py --refresh-image-id post-uuid    # Replace image by post ID
    python generator.py --batch topics.txt              # Batch from file
    python generator.py --interactive                   # Interactive mode
    python generator.py --status                        # Show queue status

Examples:
    python generator.py "How to fix a slice"
    python generator.py --autonomous --verbose
    python generator.py --backfill-images-all
    python generator.py --backfill-links-all
    python generator.py --cleanup-image my-bad-post
    python generator.py --cleanup-image-id 12e552ce-e7cf-4a42-a98a-6855f11d8708
    python generator.py --refresh-image my-bad-post -v
    python generator.py --refresh-image-id 12e552ce-e7cf-4a42-a98a-6855f11d8708
"""

import asyncio
import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    validate_config,
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    MAX_TURNS,
    DEFAULT_AUTHOR_SLUG,
    DEFAULT_STATUS,
    DEFAULT_CATEGORY_SLUG,
    ALLOW_NEW_CATEGORIES,
    ENABLE_IMAGE_GENERATION,
    BLOGS_PER_RUN,
    NICHE_PROMPT_PATH,
    ENABLE_SHOPIFY_SYNC,
    ENABLE_WORDPRESS_SYNC,
    ENABLE_LINK_BUILDING,
)
from tools.query_tools import QUERY_TOOLS
from tools.write_tools import WRITE_TOOLS
from tools.idea_tools import IDEA_TOOLS, get_pending_idea_count
from tools.image_tools import IMAGE_TOOLS
from tools.link_tools import LINK_TOOLS, BACKFILL_LINK_TOOLS


async def health_check(verbose: bool = False) -> dict:
    """
    Verify all required services are reachable before starting.
    Returns dict with status and any errors.
    """
    import aiohttp
    from config import SUPABASE_URL, get_supabase_headers, GEMINI_API_KEY

    errors = []

    # Check Supabase connectivity
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_categories?select=id&limit=1",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    errors.append(f"Supabase error: HTTP {resp.status}")
                elif verbose:
                    print("✓ Supabase connected")
    except Exception as e:
        errors.append(f"Supabase unreachable: {str(e)}")

    # Check Gemini key exists (if image generation enabled)
    if ENABLE_IMAGE_GENERATION:
        if not GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY not set but ENABLE_IMAGE_GENERATION=true")
        elif verbose:
            print("✓ Gemini API key configured")

    # Check Shopify config (if sync enabled)
    if ENABLE_SHOPIFY_SYNC:
        from config import SHOPIFY_STORE, SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET
        if not SHOPIFY_STORE:
            errors.append("SHOPIFY_STORE not set but ENABLE_SHOPIFY_SYNC=true")
        elif not SHOPIFY_CLIENT_ID:
            errors.append("SHOPIFY_CLIENT_ID not set but ENABLE_SHOPIFY_SYNC=true")
        elif not SHOPIFY_CLIENT_SECRET:
            errors.append("SHOPIFY_CLIENT_SECRET not set but ENABLE_SHOPIFY_SYNC=true")
        elif verbose:
            print("✓ Shopify credentials configured")

    # Check WordPress config (if sync enabled)
    if ENABLE_WORDPRESS_SYNC:
        from config import WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_APP_PASSWORD
        if not WORDPRESS_URL:
            errors.append("WORDPRESS_URL not set but ENABLE_WORDPRESS_SYNC=true")
        elif not WORDPRESS_USERNAME:
            errors.append("WORDPRESS_USERNAME not set but ENABLE_WORDPRESS_SYNC=true")
        elif not WORDPRESS_APP_PASSWORD:
            errors.append("WORDPRESS_APP_PASSWORD not set but ENABLE_WORDPRESS_SYNC=true")
        elif verbose:
            print("✓ WordPress credentials configured")

    # Check Link Building config (if enabled)
    if ENABLE_LINK_BUILDING:
        from config import INTERNAL_LINK_PATTERN, LINK_VALIDATION_TIMEOUT
        if verbose:
            print(f"✓ Link building enabled (pattern: {INTERNAL_LINK_PATTERN})")

    if errors:
        return {"success": False, "errors": errors}

    if verbose:
        print("✓ Health check passed\n")

    return {"success": True, "errors": []}


def load_system_prompt(verbose: bool = False) -> str:
    """Load the system prompt from file, merging with niche prompt if configured"""
    prompt_path = Path(__file__).parent / "prompts" / "system_prompt.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        base_prompt = f.read()

    # Load niche-specific prompt if configured
    niche_path = NICHE_PROMPT_PATH
    if niche_path:
        niche_full_path = Path(__file__).parent / niche_path
        if niche_full_path.exists():
            with open(niche_full_path, "r", encoding="utf-8") as f:
                niche_prompt = f.read()
            if verbose:
                print(f"✓ Niche prompt loaded: {niche_path}")
            # Merge: base prompt + separator + niche prompt
            return f"{base_prompt}\n\n---\n\n{niche_prompt}"
        else:
            print(f"⚠ Warning: Niche prompt not found at {niche_full_path}")
    elif verbose:
        print("✗ No niche prompt configured (generic mode)")

    return base_prompt


def get_all_tools(include_idea_tools: bool = True, verbose: bool = False) -> list:
    """Combine all tool definitions"""
    tools = QUERY_TOOLS + WRITE_TOOLS
    if include_idea_tools:
        tools = tools + IDEA_TOOLS
    if ENABLE_IMAGE_GENERATION:
        tools = tools + IMAGE_TOOLS
        if verbose:
            print("✓ Image generation enabled")
    elif verbose:
        print("✗ Image generation disabled (set ENABLE_IMAGE_GENERATION=true to enable)")
    if ENABLE_LINK_BUILDING:
        tools = tools + LINK_TOOLS
        if verbose:
            print("✓ Link building enabled")
    elif verbose:
        print("✗ Link building disabled (set ENABLE_LINK_BUILDING=true to enable)")
    return tools


async def execute_tool(tool_name: str, tool_input: dict, tool_list: list) -> dict:
    """Execute a tool by name and return the result"""
    for tool in tool_list:
        if tool["name"] == tool_name:
            return await tool["function"](tool_input)

    return {
        "content": [{
            "type": "text",
            "text": f"Unknown tool: {tool_name}"
        }],
        "is_error": True
    }


async def release_claimed_idea(idea_id: str, error_message: str, verbose: bool = False) -> None:
    """Release a claimed idea back to the queue on failure."""
    from tools.idea_tools import fail_blog_idea

    if verbose:
        print(f"Releasing claimed idea {idea_id}: {error_message}")

    try:
        await fail_blog_idea({"idea_id": idea_id, "error_message": error_message})
    except Exception as e:
        if verbose:
            print(f"Warning: Failed to release idea: {e}")


async def run_agent(
    initial_message: str,
    verbose: bool = False,
    include_idea_tools: bool = True,
    tools_override: list = None
) -> dict:
    """
    Run the Claude agent with the given initial message.

    This implements a simple agent loop that:
    1. Sends the message to Claude with the system prompt
    2. Executes any tools Claude requests
    3. Returns results to Claude
    4. Repeats until Claude is done or max turns reached

    Args:
        initial_message: The instruction for Claude
        verbose: Whether to print progress
        include_idea_tools: Whether to include idea queue tools
        tools_override: Optional list of tools to use instead of default

    Returns:
        dict with success status and details
    """
    try:
        import anthropic
    except ImportError:
        print("Error: anthropic package not installed.")
        print("Run: pip install anthropic")
        return {"success": False, "error": "anthropic package not installed"}

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    system_prompt = load_system_prompt(verbose=verbose)

    # Build tool definitions for API
    # Use tools_override if provided, otherwise use default tools
    tool_source = tools_override if tools_override else get_all_tools(include_idea_tools, verbose=verbose)
    tools = []
    for tool in tool_source:
        tools.append({
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": tool["input_schema"]
        })

    # Cache tool definitions (saves ~90% on tools after first turn)
    if tools:
        tools[-1]["cache_control"] = {"type": "ephemeral"}

    messages = [{"role": "user", "content": initial_message}]

    turn_count = 0
    created_post_id = None
    idea_id = None

    try:
        while turn_count < MAX_TURNS:
            turn_count += 1

            if verbose:
                print(f"\n--- Turn {turn_count}/{MAX_TURNS} ---")

            # Call Claude with prompt caching enabled
            # System prompt is cached after first turn, saving ~90% on subsequent turns
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=16384,
                system=[{
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }],
                tools=tools,
                messages=messages
            )

            # Check stop reason
            if response.stop_reason == "end_turn":
                final_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text += block.text

                if verbose:
                    print(f"\nFinal response:\n{final_text}")

                return {
                    "success": True,
                    "post_id": created_post_id,
                    "idea_id": idea_id,
                    "message": final_text,
                    "turns": turn_count
                }

            elif response.stop_reason == "tool_use":
                assistant_content = response.content
                messages.append({"role": "assistant", "content": assistant_content})

                tool_results = []
                for block in assistant_content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input

                        if verbose:
                            print(f"Tool: {tool_name}")
                            if tool_name != "create_blog_post":
                                print(f"Input: {json.dumps(tool_input, indent=2)[:500]}...")
                            else:
                                print(f"Input: (blog post content - {len(json.dumps(tool_input))} chars)")

                        result = await execute_tool(tool_name, tool_input, tool_source)

                        result_text = ""
                        is_error = result.get("is_error", False)
                        for content in result.get("content", []):
                            if content.get("type") == "text":
                                result_text += content.get("text", "")

                        if verbose:
                            print(f"Result: {result_text[:300]}...")

                        # Track IDs
                        if tool_name == "create_blog_post" and not is_error:
                            if "Created:" in result_text:
                                # Format: "Created: {id} ({slug})"
                                created_post_id = result_text.split("Created:")[1].strip().split()[0]

                        # Track claimed idea (combined tool)
                        if tool_name == "get_and_claim_blog_idea" and "ID:" in result_text:
                            for line in result_text.split("\n"):
                                if line.startswith("ID:"):
                                    idea_id = line.split("ID:")[1].strip()
                                    break

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_text,
                            "is_error": is_error
                        })

                messages.append({"role": "user", "content": tool_results})

            else:
                if verbose:
                    print(f"Unknown stop reason: {response.stop_reason}")
                break

        # Loop ended without success - release claimed idea
        error_msg = f"Max turns ({MAX_TURNS}) reached without completion"
        if idea_id and include_idea_tools:
            await release_claimed_idea(idea_id, error_msg, verbose)

        return {
            "success": False,
            "error": error_msg,
            "post_id": created_post_id,
            "idea_id": idea_id,
            "turns": turn_count
        }

    except Exception as e:
        # Unexpected error - release claimed idea
        error_msg = f"Unexpected error: {str(e)}"
        if idea_id and include_idea_tools:
            await release_claimed_idea(idea_id, error_msg, verbose)

        return {
            "success": False,
            "error": error_msg,
            "post_id": created_post_id,
            "idea_id": idea_id,
            "turns": turn_count
        }


async def generate_blog_post(topic: str, verbose: bool = False) -> dict:
    """Generate a blog post about a specific topic (manual mode)"""

    initial_message = f"""Generate a comprehensive blog post about: {topic}

Instructions:
1. First, call get_blog_context to understand existing categories, tags, and authors
2. Plan your content structure based on what already exists
3. Check your chosen slug doesn't already exist with check_slug_exists
4. Create a high-quality, SEO-optimized blog post using create_blog_post (pass tag_ids to link tags)

Configuration:
- Default author slug: {DEFAULT_AUTHOR_SLUG}
- Default post status: {DEFAULT_STATUS}
- Default fallback category: {DEFAULT_CATEGORY_SLUG}
- Can create new categories: {ALLOW_NEW_CATEGORIES}

Begin by getting the blog context."""

    return await run_agent(initial_message, verbose=verbose, include_idea_tools=False)


async def process_idea_queue(count: int = 1, verbose: bool = False) -> list:
    """
    Process ideas from the blog ideas queue (autonomous mode).

    Args:
        count: Maximum number of ideas to process
        verbose: Print detailed progress

    Returns:
        List of results for each processed idea
    """
    results = []

    # Pre-flight check: count available ideas BEFORE starting any agents
    # This saves tokens by not invoking the AI if there's nothing to process
    pending_count, error = await get_pending_idea_count()

    if error:
        # Log warning but proceed anyway - the agent will handle empty queue gracefully
        print(f"Warning: {error}")
        print("Proceeding with requested count - agent will handle if queue is empty")
        actual_count = count
    elif pending_count == 0:
        print("No pending ideas in queue - skipping autonomous run")
        return results
    else:
        # Adjust count to available ideas
        actual_count = min(count, pending_count)
        if actual_count < count:
            print(f"Requested {count} ideas but only {pending_count} available - processing {actual_count}")

    for i in range(actual_count):
        print(f"\n{'='*50}")
        print(f"Processing idea {i+1}/{actual_count}")
        print("="*50)

        initial_message = f"""You are in AUTONOMOUS MODE. Process the next blog idea from the queue.

Workflow:
1. Call get_and_claim_blog_idea to get and claim the next pending idea
2. If the queue is empty, respond that there are no ideas to process
3. Call get_blog_context to see existing categories, tags, and authors
4. Generate the blog post based on the idea's topic (and description/notes if provided)
5. Select category from existing ones (prefer reusing, rarely create new)
6. Select tags from existing ones (can create new more liberally to build relevancy)
7. Create the post with create_blog_post (pass tag_ids to link tags in same call)
8. Call complete_blog_idea with the idea_id and blog_post_id

If anything fails, call fail_blog_idea with the error message.
If the idea should be skipped (duplicate, inappropriate), call skip_blog_idea with reason.

Configuration:
- Default author slug: {DEFAULT_AUTHOR_SLUG}
- Default post status: {DEFAULT_STATUS}
- Default fallback category: {DEFAULT_CATEGORY_SLUG}
- Can create new categories: {ALLOW_NEW_CATEGORIES}

Begin by getting the next blog idea."""

        result = await run_agent(initial_message, verbose=verbose, include_idea_tools=True)
        result["iteration"] = i + 1
        results.append(result)

        if result["success"]:
            print(f"SUCCESS - Post ID: {result.get('post_id', 'unknown')}")
        else:
            error_msg = result.get("error", result.get("message", "unknown error"))
            if "queue is empty" in error_msg.lower() or "no pending" in error_msg.lower():
                print("Queue is empty - no more ideas to process")
                break
            print(f"FAILED - {error_msg[:100]}")

    return results


async def get_queue_status() -> None:
    """Display the current status of the blog ideas queue"""
    from tools.idea_tools import get_idea_queue_status

    result = await get_idea_queue_status({})
    for content in result.get("content", []):
        if content.get("type") == "text":
            print(content.get("text", ""))


def _extract_core_subject(title: str) -> str:
    """
    Extract the core subject from a blog title by removing common filler words.
    Used for both image prompts and alt text generation.
    """
    # Remove common article-type words that aren't descriptive
    cleanup_words = [
        "complete guide", "guide to", "how to", "what is", "what are",
        "explained", "tips", "tricks", "best", "top", "ultimate",
        ": complete", "- complete", "for beginners", "for experts",
    ]

    subject = title.lower()
    for word in cleanup_words:
        subject = subject.replace(word.lower(), "")

    # Clean up extra spaces and punctuation
    subject = " ".join(subject.split()).strip(" :-")

    return subject


def _create_scene_prompt(title: str, excerpt: str = "") -> str:
    """
    Create a scene-based image prompt from a blog title.

    Avoids words like "article", "blog", "guide" that cause Gemini to render text.
    Instead focuses on describing a visual scene related to the topic.
    """
    scene_base = _extract_core_subject(title)

    # Build a scene description
    if scene_base:
        prompt = f"A beautiful photograph depicting {scene_base}, cinematic composition, hero image style"
    else:
        # Fallback to excerpt if title cleanup removed everything
        prompt = f"A beautiful photograph related to: {excerpt[:150]}, cinematic composition"

    return prompt


def _create_alt_text(title: str, excerpt: str = "") -> str:
    """
    Create SEO-friendly alt text for a featured image.

    Returns a descriptive alt text based on the blog's core subject,
    NOT a lazy "Featured image for [title]" format.
    """
    subject = _extract_core_subject(title)

    if subject:
        # Capitalize first letter and create descriptive alt
        alt_text = subject[0].upper() + subject[1:] if len(subject) > 1 else subject.upper()
        return alt_text
    elif excerpt:
        # Fallback to excerpt-based description
        clean_excerpt = excerpt[:100].strip()
        if clean_excerpt:
            return clean_excerpt[0].upper() + clean_excerpt[1:] if len(clean_excerpt) > 1 else clean_excerpt

    # Last resort fallback (shouldn't happen often)
    return f"Featured image for {title}"


async def generate_image_prompt_and_alt(title: str, excerpt: str = "", verbose: bool = False) -> tuple[str, str]:
    """
    Use Claude to generate an image prompt and alt text for a blog post.

    This ensures backfilled images have the same quality as new posts created
    by the Claude agent - both use AI creativity for prompt and alt generation.

    Args:
        title: The blog post title
        excerpt: The blog post excerpt/summary
        verbose: Print debug info

    Returns:
        Tuple of (image_prompt, alt_text)
        Falls back to programmatic generation if API call fails
    """
    try:
        import anthropic
    except ImportError:
        if verbose:
            print("anthropic not installed, using fallback")
        return _create_scene_prompt(title, excerpt), _create_alt_text(title, excerpt)

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        prompt = f"""Given this blog post, generate two things:

1. IMAGE_PROMPT: A detailed prompt for generating a featured image. Describe a realistic photograph or scene that would visually represent the topic. Focus on visual elements (lighting, composition, subjects, setting). Do NOT include text, words, or typography in the image. Avoid words like "article", "blog", "guide" that might cause text to render.

2. ALT_TEXT: A concise, SEO-friendly alt text that describes what the image shows. This should be descriptive of the image content itself, NOT "Featured image for [title]". Keep it under 125 characters.

Blog Title: {title}
Blog Excerpt: {excerpt[:300] if excerpt else 'No excerpt available'}

Respond in exactly this format:
IMAGE_PROMPT: [your image prompt here]
ALT_TEXT: [your alt text here]"""

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse response
        response_text = response.content[0].text
        lines = response_text.strip().split("\n")

        image_prompt = None
        alt_text = None

        for line in lines:
            if line.startswith("IMAGE_PROMPT:"):
                image_prompt = line.replace("IMAGE_PROMPT:", "").strip()
            elif line.startswith("ALT_TEXT:"):
                alt_text = line.replace("ALT_TEXT:", "").strip()

        # Validate we got both
        if image_prompt and alt_text:
            if verbose:
                print(f"Claude generated prompt: {image_prompt[:80]}...")
                print(f"Claude generated alt: {alt_text}")
            return image_prompt, alt_text
        else:
            if verbose:
                print("Could not parse Claude response, using fallback")
            return _create_scene_prompt(title, excerpt), _create_alt_text(title, excerpt)

    except Exception as e:
        if verbose:
            print(f"Claude API error: {e}, using fallback")
        return _create_scene_prompt(title, excerpt), _create_alt_text(title, excerpt)


async def backfill_images(count: int = 1, verbose: bool = False) -> list:
    """
    Generate images for posts that don't have them.

    Args:
        count: Maximum number of posts to process
        verbose: Print detailed progress

    Returns:
        List of results for each processed post
    """
    from tools.query_tools import get_posts_without_images
    from tools.write_tools import update_post_image
    from tools.image_tools import generate_featured_image

    if not ENABLE_IMAGE_GENERATION:
        print("Image generation is disabled. Set ENABLE_IMAGE_GENERATION=true")
        return []

    # Get posts without images
    posts = await get_posts_without_images(limit=count)

    if not posts:
        print("No posts found without images.")
        return []

    print(f"Found {len(posts)} post(s) without images")

    results = []
    for i, post in enumerate(posts, 1):
        print(f"\n{'='*50}")
        print(f"[{i}/{len(posts)}] {post['title'][:50]}...")
        print("="*50)

        post_id = post["id"]
        slug = post["slug"]
        title = post["title"]
        excerpt = post.get("excerpt", "")

        # Get category slug from nested relation
        category_data = post.get("blog_categories")
        category_slug = category_data.get("slug") if category_data else "general"

        # Use Claude to generate image prompt and alt text (same as new posts)
        print("Generating image prompt and alt text with Claude...")
        prompt, alt_text = await generate_image_prompt_and_alt(title, excerpt, verbose=verbose)

        if verbose:
            print(f"Category: {category_slug}")
            print(f"Prompt: {prompt[:100]}...")

        # Generate image
        result = await generate_featured_image({
            "prompt": prompt,
            "category_slug": category_slug,
            "post_slug": slug
        })

        # Check result
        result_text = ""
        for content in result.get("content", []):
            if content.get("type") == "text":
                result_text = content.get("text", "")

        if "SKIPPED" in result_text:
            print(f"SKIPPED - {result_text}")
            results.append({"post_id": post_id, "success": False, "error": result_text})
            continue

        # Extract URL from result
        if "URL:" in result_text:
            lines = result_text.split("\n")
            image_url = None
            for line in lines:
                if line.startswith("URL:"):
                    image_url = line.split("URL:")[1].strip()
                    break

            if image_url:
                # Update the post with Claude-generated alt text
                success = await update_post_image(post_id, image_url, alt_text)

                if success:
                    print(f"SUCCESS - {image_url}")
                    results.append({"post_id": post_id, "success": True, "image_url": image_url})
                else:
                    print(f"FAILED - Could not update post")
                    results.append({"post_id": post_id, "success": False, "error": "Update failed"})
            else:
                print(f"FAILED - Could not extract URL from result")
                results.append({"post_id": post_id, "success": False, "error": "No URL in result"})
        else:
            print(f"FAILED - Unexpected result: {result_text[:100]}")
            results.append({"post_id": post_id, "success": False, "error": result_text})

    # Summary
    print("\n" + "="*50)
    print("BACKFILL SUMMARY")
    print("="*50)
    successful = sum(1 for r in results if r.get("success"))
    print(f"Processed: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {len(results) - successful}")

    return results


async def backfill_links(count: int = 5, verbose: bool = False) -> list:
    """
    Add internal links to posts that have fewer than recommended.
    Uses Claude to intelligently add links without breaking existing content.

    Args:
        count: Maximum number of posts to process
        verbose: Print detailed progress

    Returns:
        List of results for each processed post
    """
    from tools.link_tools import get_posts_needing_links

    if not ENABLE_LINK_BUILDING:
        print("Link building is disabled. Set ENABLE_LINK_BUILDING=true")
        return []

    # Get posts that need more links
    result = await get_posts_needing_links({"limit": count})
    result_text = result.get("content", [{}])[0].get("text", "{}")

    import json
    try:
        data = json.loads(result_text)
    except json.JSONDecodeError:
        print(f"Error parsing posts: {result_text}")
        return []

    posts = data.get("posts", [])
    catalog_size = data.get("catalog_size", 0)
    catalog_note = data.get("note")

    if not posts:
        message = data.get("message", "No posts need link improvements")
        print(message)
        return []

    print(f"Found {len(posts)} post(s) needing link improvements")
    if catalog_note:
        print(f"Note: {catalog_note}")

    results = []
    for i, post in enumerate(posts, 1):
        print(f"\n{'='*50}")
        print(f"[{i}/{len(posts)}] {post['title']}")
        print(f"Current: {post['current_links']} links | Target: {post['recommended']} | To add: {post['deficit']}")
        print("="*50)

        # Build the agent prompt for this post
        # The recommended/deficit are already adjusted for catalog size
        links_to_add = post['deficit']
        prompt = f"""You are enhancing internal links for an existing blog post.

POST TO ENHANCE:
- ID: {post['id']}
- Title: {post['title']}
- Links to add: up to {links_to_add}

WORKFLOW:
1. Call `get_post_for_linking` with post_id "{post['id']}" to get the content
2. Call `get_internal_link_suggestions` with:
   - topic: "{post['title']}"
   - exclude_slug: the post's slug

Suggestions include semantic disambiguation data (example pattern - apply to your content):
```
{{
  "url": "/blog/how-to-grip-golf-club",
  "title": "How to Grip a Golf Club",
  "anchor_patterns": ["grip technique", "hand position"],
  "anti_patterns": ["grip on the club", "lose your grip"],
  "semantic_intent": "hand positioning technique"
}}
```

- `anchor_patterns`: Phrases to search for in content
- `anti_patterns`: Phrases that look similar but have DIFFERENT meanings - SKIP these
- `semantic_intent`: What the target article actually teaches

3. For EACH suggestion:
   - Search content for `anchor_patterns` (case-insensitive)
   - If found phrase matches any `anti_pattern`, SKIP it (different semantic meaning)
4. Call `validate_urls` with your planned URLs
5. Call `apply_link_insertions` - include ALL fields for semantic validation:
```
{{"insertions": [{{
  "anchor_text": "found phrase",
  "url": "/blog/slug",
  "target_title": "Article Title",
  "anti_patterns": ["phrase to avoid", "another avoid"]
}}]}}
```

The system performs two-stage validation:
1. Anti-pattern filter (fast, deterministic)
2. AI semantic validation (checks if meaning matches)

RULES:
- Only link phrases that naturally appear in the content
- Use `anchor_patterns` provided - don't invent random phrases
- SKIP any phrase that matches an `anti_pattern` (semantic mismatch)
- Always include `target_title` AND `anti_patterns` in each insertion
- If a pattern isn't found, skip that suggestion
- If no patterns match, respond: "Skipping - no matching phrases found"

The anchor text meaning must match what the target article teaches."""

        # Run the agent with backfill tools
        agent_result = await run_agent(
            initial_message=prompt,
            verbose=verbose,
            include_idea_tools=False,
            tools_override=BACKFILL_LINK_TOOLS
        )

        if agent_result.get("success"):
            # Try to extract link count from the message
            message = agent_result.get("message", "")
            if "applied" in message.lower():
                print(f"SUCCESS - {message[:100]}")
            else:
                print(f"SUCCESS - Links enhanced")
            results.append({"post_id": post['id'], "success": True, "message": message})
        else:
            error = agent_result.get("error", agent_result.get("message", "Unknown error"))
            if "skip" in str(error).lower():
                print(f"SKIPPED - {error[:80]}")
                results.append({"post_id": post['id'], "success": True, "skipped": True})
            else:
                print(f"FAILED - {error[:80]}")
                results.append({"post_id": post['id'], "success": False, "error": error})

    # Summary
    print("\n" + "="*50)
    print("LINK BACKFILL SUMMARY")
    print("="*50)
    enhanced = sum(1 for r in results if r.get("success") and not r.get("skipped"))
    skipped = sum(1 for r in results if r.get("skipped"))
    failed = sum(1 for r in results if not r.get("success"))
    print(f"Processed: {len(results)}")
    print(f"Enhanced: {enhanced}")
    if skipped:
        print(f"Skipped: {skipped}")
    if failed:
        print(f"Failed: {failed}")

    return results


async def backfill_links_single(
    post_id: str = None,
    post_slug: str = None,
    verbose: bool = False
) -> dict:
    """
    Add internal links to a specific post by ID or slug.

    Args:
        post_id: Post UUID (optional if post_slug provided)
        post_slug: Post slug (optional if post_id provided)
        verbose: Print detailed progress

    Returns:
        Result dict with success status
    """
    import aiohttp
    from config import SUPABASE_URL, get_supabase_headers

    if not ENABLE_LINK_BUILDING:
        print("Link building is disabled. Set ENABLE_LINK_BUILDING=true")
        return {"success": False, "error": "Link building disabled"}

    if not post_id and not post_slug:
        print("Error: Must provide either post_id or post_slug")
        return {"success": False, "error": "No post identifier provided"}

    # Fetch the post
    async with aiohttp.ClientSession() as session:
        headers = get_supabase_headers()

        if post_id:
            query = f"id=eq.{post_id}"
        else:
            query = f"slug=eq.{post_slug}"

        async with session.get(
            f"{SUPABASE_URL}/rest/v1/blog_posts?{query}&select=id,slug,title,status",
            headers=headers
        ) as resp:
            if resp.status != 200:
                print(f"Error fetching post: HTTP {resp.status}")
                return {"success": False, "error": "Failed to fetch post"}
            posts = await resp.json()

        if not posts:
            print(f"Post not found")
            return {"success": False, "error": "Post not found"}

        post = posts[0]

        # Count current internal links
        async with session.get(
            f"{SUPABASE_URL}/rest/v1/blog_post_links?post_id=eq.{post['id']}&link_type=eq.internal&select=id",
            headers={**headers, "Prefer": "count=exact"}
        ) as resp:
            content_range = resp.headers.get("content-range", "")
            current_links = 0
            if "/" in content_range:
                try:
                    total = content_range.split("/")[1]
                    current_links = int(total) if total != "*" else 0
                except (ValueError, IndexError):
                    pass

    # Build post info for the backfill prompt
    post_info = {
        "id": post["id"],
        "title": post["title"],
        "slug": post["slug"],
        "current_links": current_links,
        "recommended": 5,  # Default target
        "deficit": max(0, 5 - current_links)
    }

    print(f"\n{'='*50}")
    print(f"Post: {post_info['title']}")
    print(f"Current: {post_info['current_links']} links | Target: {post_info['recommended']} | To add: {post_info['deficit']}")
    print("="*50)

    if post_info['deficit'] == 0:
        print("Post already has enough internal links.")
        return {"success": True, "message": "Already has enough links"}

    # Build the agent prompt
    links_to_add = post_info['deficit']
    prompt = f"""You are enhancing internal links for an existing blog post.

POST TO ENHANCE:
- ID: {post_info['id']}
- Title: {post_info['title']}
- Links to add: up to {links_to_add}

WORKFLOW:
1. Call `get_post_for_linking` with post_id "{post_info['id']}" to get the content
2. Call `get_internal_link_suggestions` with:
   - topic: "{post_info['title']}"
   - exclude_slug: "{post_info['slug']}"

The suggestions are PRE-FILTERED for semantic relevance. Each includes `anchor_patterns` to search for.

3. For EACH suggestion, search the content for its anchor_patterns (case-insensitive)
4. Call `validate_urls` with your planned URLs
5. Call `apply_link_insertions` - IMPORTANT: include `target_title` for context validation

RULES:
- Only link phrases that naturally appear in the content
- Use the `anchor_patterns` provided - don't invent random phrases
- Always include `target_title` in each insertion
- If no patterns match, respond: "Skipping - no matching phrases found"
"""

    # Run the agent with backfill tools
    agent_result = await run_agent(
        initial_message=prompt,
        verbose=verbose,
        include_idea_tools=False,
        tools_override=BACKFILL_LINK_TOOLS
    )

    if agent_result.get("success"):
        message = agent_result.get("message", "")
        if "applied" in message.lower():
            print(f"SUCCESS - {message[:100]}")
        else:
            print(f"SUCCESS - Links enhanced")
        return {"success": True, "message": message}
    else:
        error = agent_result.get("error", agent_result.get("message", "Unknown error"))
        if "skip" in str(error).lower():
            print(f"SKIPPED - {error[:80]}")
            return {"success": True, "skipped": True}
        else:
            print(f"FAILED - {error[:80]}")
            return {"success": False, "error": error}


async def generate_batch(topics_file: str, verbose: bool = False) -> list:
    """Generate multiple blog posts from a file of topics"""
    with open(topics_file, "r", encoding="utf-8") as f:
        topics = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    print(f"Generating {len(topics)} blog posts...")

    results = []
    for i, topic in enumerate(topics, 1):
        print(f"\n{'='*50}")
        print(f"[{i}/{len(topics)}] Topic: {topic}")
        print("="*50)

        result = await generate_blog_post(topic, verbose=verbose)
        result["topic"] = topic
        results.append(result)

        if result["success"]:
            print(f"SUCCESS - Post ID: {result.get('post_id', 'unknown')}")
        else:
            print(f"FAILED - {result.get('error', 'unknown error')}")

    # Summary
    print("\n" + "="*50)
    print("BATCH SUMMARY")
    print("="*50)
    successful = sum(1 for r in results if r["success"])
    print(f"Successful: {successful}/{len(topics)}")

    return results


async def interactive_mode(verbose: bool = False) -> None:
    """Interactive mode for generating posts one at a time"""
    print("Autonomous Blog Generator - Interactive Mode")
    print("Commands: 'quit', 'status', 'auto' (process one from queue)")
    print("-" * 50)

    while True:
        user_input = input("\nEnter blog topic (or command): ").strip()

        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break

        if user_input.lower() == "status":
            await get_queue_status()
            continue

        if user_input.lower() == "auto":
            results = await process_idea_queue(count=1, verbose=verbose)
            continue

        if not user_input:
            print("Please enter a topic or command.")
            continue

        print(f"\nGenerating blog post about: {user_input}")
        print("-" * 40)

        result = await generate_blog_post(user_input, verbose=verbose)

        if result["success"]:
            print(f"\nSUCCESS!")
            print(f"Post ID: {result.get('post_id', 'check database')}")
            print(f"Turns used: {result.get('turns', 'unknown')}")
        else:
            print(f"\nFAILED: {result.get('error', 'unknown error')}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Generate blog posts using Claude AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  MANUAL:         python generator.py "How to fix your slice"
  AUTONOMOUS:     python generator.py --autonomous
  BACKFILL IMG:   python generator.py --backfill-images
  BACKFILL LINKS: python generator.py --backfill-links
  CLEANUP LINKS:  python generator.py --cleanup-links-all
  CLEANUP IMAGE:  python generator.py --cleanup-image <slug> | --cleanup-image-id <uuid>
  REFRESH IMAGE:  python generator.py --refresh-image <slug> | --refresh-image-id <uuid>
  BATCH:          python generator.py --batch topics.txt
  INTERACTIVE:    python generator.py --interactive
  STATUS:         python generator.py --status

Examples:
  # Generate one post about a specific topic
  python generator.py "Best putting drills for beginners" --verbose

  # Process the next idea from the queue
  python generator.py --autonomous

  # Process up to 5 ideas from the queue
  python generator.py --autonomous --count 5

  # Generate images for posts missing them
  python generator.py --backfill-images --count 10
  python generator.py --backfill-images-all

  # Add internal links to posts
  python generator.py --backfill-links --count 5
  python generator.py --backfill-links-all

  # Remove bad internal links (then re-run backfill)
  python generator.py --cleanup-links post-slug
  python generator.py --cleanup-links-id post-uuid
  python generator.py --cleanup-links-all

  # Remove a single link by its blog_post_links table ID
  python generator.py --remove-link link-uuid

  # Remove bad featured image (clears DB + deletes from storage)
  python generator.py --cleanup-image post-slug
  python generator.py --cleanup-image-id post-uuid

  # Replace bad featured image (cleanup + generate new in one command)
  python generator.py --refresh-image post-slug
  python generator.py --refresh-image-id post-uuid

  # Check queue status
  python generator.py --status
        """
    )

    parser.add_argument(
        "topic",
        nargs="?",
        help="The topic to write a blog post about (manual mode)"
    )
    parser.add_argument(
        "--autonomous", "-a",
        action="store_true",
        help="Process ideas from the blog_ideas queue"
    )
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=BLOGS_PER_RUN,
        help=f"Number of blogs to generate (default: {BLOGS_PER_RUN}, set via BLOGS_PER_RUN env var)"
    )
    parser.add_argument(
        "--batch",
        metavar="FILE",
        help="Generate posts from a file (one topic per line)"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show the blog ideas queue status"
    )
    parser.add_argument(
        "--backfill-images",
        action="store_true",
        help="Generate images for posts that don't have them (use --count to limit)"
    )
    parser.add_argument(
        "--backfill-images-all",
        action="store_true",
        help="Generate images for ALL posts that don't have them"
    )
    parser.add_argument(
        "--backfill-links",
        action="store_true",
        help="Add internal links to posts that have fewer than recommended (use --count to limit)"
    )
    parser.add_argument(
        "--backfill-links-all",
        action="store_true",
        help="Add internal links to ALL posts that need them"
    )
    parser.add_argument(
        "--backfill-links-id",
        type=str,
        metavar="UUID",
        help="Add internal links to a specific post by ID"
    )
    parser.add_argument(
        "--backfill-links-slug",
        type=str,
        metavar="SLUG",
        help="Add internal links to a specific post by slug"
    )
    parser.add_argument(
        "--cleanup-links",
        type=str,
        metavar="SLUG",
        help="Remove internal links from a post by slug"
    )
    parser.add_argument(
        "--cleanup-links-id",
        type=str,
        metavar="UUID",
        help="Remove internal links from a post by ID"
    )
    parser.add_argument(
        "--cleanup-links-all",
        action="store_true",
        help="Remove internal links from ALL published posts"
    )
    parser.add_argument(
        "--remove-link",
        type=str,
        metavar="LINK_UUID",
        help="Remove a single link by its blog_post_links table ID"
    )
    parser.add_argument(
        "--cleanup-image",
        type=str,
        metavar="SLUG",
        help="Remove featured image from a post by slug (clears DB + deletes from storage)"
    )
    parser.add_argument(
        "--cleanup-image-id",
        type=str,
        metavar="UUID",
        help="Remove featured image from a post by ID (clears DB + deletes from storage)"
    )
    parser.add_argument(
        "--refresh-image",
        type=str,
        metavar="SLUG",
        help="Replace featured image for a post by slug (cleanup + generate new)"
    )
    parser.add_argument(
        "--refresh-image-id",
        type=str,
        metavar="UUID",
        help="Replace featured image for a post by ID (cleanup + generate new)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed progress"
    )

    # Shopify sync arguments
    shopify_group = parser.add_argument_group('Shopify Sync')
    shopify_group.add_argument(
        "--shopify-sync",
        type=str,
        metavar="SLUG",
        help="Sync a specific post to Shopify by slug"
    )
    shopify_group.add_argument(
        "--shopify-sync-id",
        type=str,
        metavar="UUID",
        help="Sync a specific post to Shopify by ID"
    )
    shopify_group.add_argument(
        "--shopify-sync-all",
        action="store_true",
        help="Sync all posts that need syncing to Shopify"
    )
    shopify_group.add_argument(
        "--shopify-sync-recent",
        type=int,
        metavar="N",
        help="Sync the N most recently updated posts to Shopify"
    )
    shopify_group.add_argument(
        "--shopify-sync-slugs",
        type=str,
        metavar="SLUGS",
        help="Sync multiple posts by comma-separated slugs (skips missing, shows summary)"
    )
    shopify_group.add_argument(
        "--shopify-sync-categories",
        action="store_true",
        help="Sync all categories to Shopify Blogs"
    )
    shopify_group.add_argument(
        "--shopify-sync-category",
        type=str,
        metavar="SLUG",
        help="Sync a specific category to Shopify by slug"
    )
    shopify_group.add_argument(
        "--shopify-status",
        action="store_true",
        help="Show Shopify sync status of all posts"
    )
    shopify_group.add_argument(
        "--shopify-status-categories",
        action="store_true",
        help="Show Shopify sync status of all categories"
    )
    shopify_group.add_argument(
        "--shopify-import-categories",
        action="store_true",
        help="Import categories (blogs) from Shopify into Supabase"
    )
    shopify_group.add_argument(
        "--shopify-import-tags",
        action="store_true",
        help="Import tags from Shopify articles into Supabase"
    )
    shopify_group.add_argument(
        "--shopify-import-posts",
        action="store_true",
        help="Import posts (articles) from Shopify into Supabase"
    )
    shopify_group.add_argument(
        "--shopify-import-post",
        type=str,
        metavar="SLUG",
        help="Import a single post from Shopify by slug (overwrites Supabase data)"
    )
    shopify_group.add_argument(
        "--shopify-import-all",
        action="store_true",
        help="Import all content (categories, tags, posts) from Shopify into Supabase"
    )
    shopify_group.add_argument(
        "--force",
        action="store_true",
        help="Force sync even if already up-to-date (use with sync commands)"
    )
    shopify_group.add_argument(
        "--force-pull",
        action="store_true",
        help="Force overwrite Supabase data with CMS data (use with import commands)"
    )

    # WordPress sync arguments
    wordpress_group = parser.add_argument_group('WordPress Sync')
    wordpress_group.add_argument(
        "--wordpress-sync",
        type=str,
        metavar="SLUG",
        help="Sync a specific post to WordPress by slug"
    )
    wordpress_group.add_argument(
        "--wordpress-sync-id",
        type=str,
        metavar="UUID",
        help="Sync a specific post to WordPress by ID"
    )
    wordpress_group.add_argument(
        "--wordpress-sync-all",
        action="store_true",
        help="Sync all posts that need syncing to WordPress"
    )
    wordpress_group.add_argument(
        "--wordpress-sync-recent",
        type=int,
        metavar="N",
        help="Sync the N most recently updated posts to WordPress"
    )
    wordpress_group.add_argument(
        "--wordpress-sync-categories",
        action="store_true",
        help="Sync all categories to WordPress"
    )
    wordpress_group.add_argument(
        "--wordpress-sync-category",
        type=str,
        metavar="SLUG",
        help="Sync a specific category to WordPress by slug"
    )
    wordpress_group.add_argument(
        "--wordpress-status",
        action="store_true",
        help="Show WordPress sync status of all posts"
    )
    wordpress_group.add_argument(
        "--wordpress-status-categories",
        action="store_true",
        help="Show WordPress sync status of all categories"
    )
    wordpress_group.add_argument(
        "--wordpress-import-categories",
        action="store_true",
        help="Import categories from WordPress into Supabase"
    )
    wordpress_group.add_argument(
        "--wordpress-import-tags",
        action="store_true",
        help="Import tags from WordPress into Supabase"
    )
    wordpress_group.add_argument(
        "--wordpress-import-posts",
        action="store_true",
        help="Import posts from WordPress into Supabase"
    )
    wordpress_group.add_argument(
        "--wordpress-import-all",
        action="store_true",
        help="Import all content (categories, tags, posts) from WordPress into Supabase"
    )

    args = parser.parse_args()

    # Validate configuration
    try:
        validate_config()
    except ValueError as e:
        print(f"Configuration Error: {e}")
        sys.exit(1)

    # Health check (skip for status-only commands)
    skip_health_check = args.status or args.shopify_status or args.shopify_status_categories or args.wordpress_status or args.wordpress_status_categories
    if not skip_health_check:
        health = asyncio.run(health_check(verbose=args.verbose))
        if not health["success"]:
            print("Health check failed:")
            for error in health["errors"]:
                print(f"  ✗ {error}")
            sys.exit(1)

    # Run appropriate mode
    if args.status:
        asyncio.run(get_queue_status())

    # Shopify sync commands
    elif args.shopify_sync_categories:
        if not ENABLE_SHOPIFY_SYNC:
            print("Shopify sync is not enabled. Set ENABLE_SHOPIFY_SYNC=true in .env")
            sys.exit(1)
        from tools.shopify_sync import sync_all_categories
        result = asyncio.run(sync_all_categories(force=args.force))
        print(f"\nSynced: {result['synced']} | Failed: {result['failed']} | Skipped: {result['skipped']}")

    elif args.shopify_sync_category:
        if not ENABLE_SHOPIFY_SYNC:
            print("Shopify sync is not enabled. Set ENABLE_SHOPIFY_SYNC=true in .env")
            sys.exit(1)
        from tools.shopify_sync import sync_category_by_slug
        success = asyncio.run(sync_category_by_slug(args.shopify_sync_category, force=args.force))
        sys.exit(0 if success else 1)

    elif args.shopify_sync:
        if not ENABLE_SHOPIFY_SYNC:
            print("Shopify sync is not enabled. Set ENABLE_SHOPIFY_SYNC=true in .env")
            sys.exit(1)
        from tools.shopify_sync import sync_post_by_slug
        success = asyncio.run(sync_post_by_slug(args.shopify_sync, force=args.force))
        sys.exit(0 if success else 1)

    elif args.shopify_sync_id:
        if not ENABLE_SHOPIFY_SYNC:
            print("Shopify sync is not enabled. Set ENABLE_SHOPIFY_SYNC=true in .env")
            sys.exit(1)
        from tools.shopify_sync import sync_post_by_id
        success = asyncio.run(sync_post_by_id(args.shopify_sync_id, force=args.force))
        sys.exit(0 if success else 1)

    elif args.shopify_sync_all:
        if not ENABLE_SHOPIFY_SYNC:
            print("Shopify sync is not enabled. Set ENABLE_SHOPIFY_SYNC=true in .env")
            sys.exit(1)
        # SAFETY: Require confirmation for bulk sync operations
        print("\n" + "=" * 60)
        print("WARNING: BULK SHOPIFY SYNC (Supabase -> Shopify)")
        print("=" * 60)
        print("This will push posts from Supabase TO Shopify.")
        if args.force:
            print("--force flag: Will re-sync even up-to-date posts.")
        print("\nSafety checks prevent overwriting longer Shopify content")
        print("with shorter Supabase content.")
        print("=" * 60)
        confirm = input("\nType 'yes' to continue: ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)
        from tools.shopify_sync import sync_all_posts
        result = asyncio.run(sync_all_posts(force=args.force))
        print(f"\nSynced: {result['synced']} | Failed: {result['failed']} | Skipped: {result['skipped']}")

    elif args.shopify_sync_recent:
        if not ENABLE_SHOPIFY_SYNC:
            print("Shopify sync is not enabled. Set ENABLE_SHOPIFY_SYNC=true in .env")
            sys.exit(1)
        from tools.shopify_sync import sync_recent
        result = asyncio.run(sync_recent(args.shopify_sync_recent, force=args.force))
        print(f"\nSynced: {result['synced']} | Failed: {result['failed']} | Skipped: {result['skipped']}")

    elif args.shopify_sync_slugs:
        if not ENABLE_SHOPIFY_SYNC:
            print("Shopify sync is not enabled. Set ENABLE_SHOPIFY_SYNC=true in .env")
            sys.exit(1)
        from tools.shopify_sync import sync_post_by_slug, get_post_by_slug

        # Parse comma-separated slugs
        slugs = [s.strip() for s in args.shopify_sync_slugs.split(",") if s.strip()]

        if not slugs:
            print("No slugs provided")
            sys.exit(1)

        print(f"Syncing {len(slugs)} posts to Shopify...\n")

        synced = []
        failed = []
        not_found = []

        for slug in slugs:
            # First check if post exists
            post = asyncio.run(get_post_by_slug(slug))
            if not post:
                print(f"Post not found: {slug}")
                not_found.append(slug)
                continue

            success = asyncio.run(sync_post_by_slug(slug, force=args.force))
            if success:
                synced.append(slug)
            else:
                failed.append(slug)

        # Print summary
        print("\n" + "=" * 60)
        print("SYNC SUMMARY")
        print("=" * 60)
        print(f"Synced: {len(synced)} | Not Found: {len(not_found)} | Failed: {len(failed)}")

        if not_found:
            print(f"\nPosts not found in Supabase ({len(not_found)}):")
            for slug in not_found:
                print(f"  - {slug}")

        if failed:
            print(f"\nFailed to sync ({len(failed)}):")
            for slug in failed:
                print(f"  - {slug}")

        # Exit with error only if nothing succeeded
        if not synced and (not_found or failed):
            sys.exit(1)

    elif args.shopify_status:
        if not ENABLE_SHOPIFY_SYNC:
            print("Shopify sync is not enabled. Set ENABLE_SHOPIFY_SYNC=true in .env")
            sys.exit(1)
        from tools.shopify_sync import show_sync_status
        asyncio.run(show_sync_status())

    elif args.shopify_status_categories:
        if not ENABLE_SHOPIFY_SYNC:
            print("Shopify sync is not enabled. Set ENABLE_SHOPIFY_SYNC=true in .env")
            sys.exit(1)
        from tools.shopify_sync import show_category_sync_status
        asyncio.run(show_category_sync_status())

    elif args.shopify_import_categories:
        if not ENABLE_SHOPIFY_SYNC:
            print("Shopify sync is not enabled. Set ENABLE_SHOPIFY_SYNC=true in .env")
            sys.exit(1)
        from tools.shopify_sync import import_categories_from_shopify
        result = asyncio.run(import_categories_from_shopify(force_pull=args.force_pull))
        print(f"\nImported: {result['imported']} | Updated: {result['updated']} | Skipped: {result['skipped']}")

    elif args.shopify_import_tags:
        if not ENABLE_SHOPIFY_SYNC:
            print("Shopify sync is not enabled. Set ENABLE_SHOPIFY_SYNC=true in .env")
            sys.exit(1)
        from tools.shopify_sync import import_tags_from_shopify
        result = asyncio.run(import_tags_from_shopify(force_pull=args.force_pull))
        print(f"\nImported: {result['imported']} | Updated: {result['updated']} | Skipped: {result['skipped']}")

    elif args.shopify_import_posts:
        if not ENABLE_SHOPIFY_SYNC:
            print("Shopify sync is not enabled. Set ENABLE_SHOPIFY_SYNC=true in .env")
            sys.exit(1)
        # SAFETY: Require confirmation, especially with --force-pull
        if args.force_pull:
            print("\n" + "=" * 60)
            print("DANGER: IMPORT WITH --force-pull (Shopify -> Supabase)")
            print("=" * 60)
            print("This will OVERWRITE existing Supabase posts with Shopify data!")
            print("All post content and tags in Supabase will be replaced.")
            print("\nThis operation can cause data loss if Shopify data is")
            print("incomplete or corrupted.")
            print("=" * 60)
            confirm = input("\nType 'yes' to continue: ")
            if confirm.lower() != 'yes':
                print("Aborted.")
                sys.exit(0)
        from tools.shopify_sync import import_posts_from_shopify
        result = asyncio.run(import_posts_from_shopify(force_pull=args.force_pull))
        print(f"\nImported: {result['imported']} | Updated: {result['updated']} | Skipped: {result['skipped']}")

    elif args.shopify_import_post:
        if not ENABLE_SHOPIFY_SYNC:
            print("Shopify sync is not enabled. Set ENABLE_SHOPIFY_SYNC=true in .env")
            sys.exit(1)
        from tools.shopify_sync import import_single_post_from_shopify
        success = asyncio.run(import_single_post_from_shopify(args.shopify_import_post))
        if not success:
            sys.exit(1)

    elif args.shopify_import_all:
        if not ENABLE_SHOPIFY_SYNC:
            print("Shopify sync is not enabled. Set ENABLE_SHOPIFY_SYNC=true in .env")
            sys.exit(1)
        # SAFETY: Always require confirmation for bulk import
        print("\n" + "=" * 60)
        if args.force_pull:
            print("DANGER: BULK IMPORT WITH --force-pull (Shopify -> Supabase)")
        else:
            print("WARNING: BULK IMPORT (Shopify -> Supabase)")
        print("=" * 60)
        print("This will import categories, tags, and posts from Shopify.")
        if args.force_pull:
            print("\n--force-pull flag: Will OVERWRITE existing Supabase data!")
            print("This can cause data loss if Shopify data is incomplete.")
        else:
            print("\nExisting Supabase records will be SKIPPED (safe mode).")
        print("=" * 60)
        confirm = input("\nType 'yes' to continue: ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)
        from tools.shopify_sync import import_all_from_shopify
        result = asyncio.run(import_all_from_shopify(force_pull=args.force_pull))
        print(f"\n=== Shopify Import Summary ===")
        print(f"Categories - Imported: {result['categories']['imported']} | Updated: {result['categories']['updated']} | Skipped: {result['categories']['skipped']}")
        print(f"Tags       - Imported: {result['tags']['imported']} | Updated: {result['tags']['updated']} | Skipped: {result['tags']['skipped']}")
        print(f"Posts      - Imported: {result['posts']['imported']} | Updated: {result['posts']['updated']} | Skipped: {result['posts']['skipped']}")

    # WordPress sync commands
    elif args.wordpress_sync_categories:
        if not ENABLE_WORDPRESS_SYNC:
            print("WordPress sync is not enabled. Set ENABLE_WORDPRESS_SYNC=true in .env")
            sys.exit(1)
        from tools.wordpress_sync import sync_all_categories as wp_sync_all_categories
        result = asyncio.run(wp_sync_all_categories(force=args.force))
        print(f"\nSynced: {result['synced']} | Failed: {result['failed']} | Skipped: {result['skipped']}")

    elif args.wordpress_sync_category:
        if not ENABLE_WORDPRESS_SYNC:
            print("WordPress sync is not enabled. Set ENABLE_WORDPRESS_SYNC=true in .env")
            sys.exit(1)
        from tools.wordpress_sync import sync_category_by_slug as wp_sync_category_by_slug
        success = asyncio.run(wp_sync_category_by_slug(args.wordpress_sync_category, force=args.force))
        sys.exit(0 if success else 1)

    elif args.wordpress_sync:
        if not ENABLE_WORDPRESS_SYNC:
            print("WordPress sync is not enabled. Set ENABLE_WORDPRESS_SYNC=true in .env")
            sys.exit(1)
        from tools.wordpress_sync import sync_post_by_slug as wp_sync_post_by_slug
        success = asyncio.run(wp_sync_post_by_slug(args.wordpress_sync, force=args.force))
        sys.exit(0 if success else 1)

    elif args.wordpress_sync_id:
        if not ENABLE_WORDPRESS_SYNC:
            print("WordPress sync is not enabled. Set ENABLE_WORDPRESS_SYNC=true in .env")
            sys.exit(1)
        from tools.wordpress_sync import sync_post_by_id as wp_sync_post_by_id
        success = asyncio.run(wp_sync_post_by_id(args.wordpress_sync_id, force=args.force))
        sys.exit(0 if success else 1)

    elif args.wordpress_sync_all:
        if not ENABLE_WORDPRESS_SYNC:
            print("WordPress sync is not enabled. Set ENABLE_WORDPRESS_SYNC=true in .env")
            sys.exit(1)
        from tools.wordpress_sync import sync_all_posts as wp_sync_all_posts
        result = asyncio.run(wp_sync_all_posts(force=args.force))
        print(f"\nSynced: {result['synced']} | Failed: {result['failed']} | Skipped: {result['skipped']}")

    elif args.wordpress_sync_recent:
        if not ENABLE_WORDPRESS_SYNC:
            print("WordPress sync is not enabled. Set ENABLE_WORDPRESS_SYNC=true in .env")
            sys.exit(1)
        from tools.wordpress_sync import sync_recent as wp_sync_recent
        result = asyncio.run(wp_sync_recent(args.wordpress_sync_recent, force=args.force))
        print(f"\nSynced: {result['synced']} | Failed: {result['failed']} | Skipped: {result['skipped']}")

    elif args.wordpress_status:
        if not ENABLE_WORDPRESS_SYNC:
            print("WordPress sync is not enabled. Set ENABLE_WORDPRESS_SYNC=true in .env")
            sys.exit(1)
        from tools.wordpress_sync import show_sync_status as wp_show_sync_status
        asyncio.run(wp_show_sync_status())

    elif args.wordpress_status_categories:
        if not ENABLE_WORDPRESS_SYNC:
            print("WordPress sync is not enabled. Set ENABLE_WORDPRESS_SYNC=true in .env")
            sys.exit(1)
        from tools.wordpress_sync import show_category_sync_status as wp_show_category_sync_status
        asyncio.run(wp_show_category_sync_status())

    elif args.wordpress_import_categories:
        if not ENABLE_WORDPRESS_SYNC:
            print("WordPress sync is not enabled. Set ENABLE_WORDPRESS_SYNC=true in .env")
            sys.exit(1)
        from tools.wordpress_sync import import_categories_from_wordpress
        result = asyncio.run(import_categories_from_wordpress(force_pull=args.force_pull))
        print(f"\nImported: {result['imported']} | Updated: {result['updated']} | Skipped: {result['skipped']}")

    elif args.wordpress_import_tags:
        if not ENABLE_WORDPRESS_SYNC:
            print("WordPress sync is not enabled. Set ENABLE_WORDPRESS_SYNC=true in .env")
            sys.exit(1)
        from tools.wordpress_sync import import_tags_from_wordpress
        result = asyncio.run(import_tags_from_wordpress(force_pull=args.force_pull))
        print(f"\nImported: {result['imported']} | Updated: {result['updated']} | Skipped: {result['skipped']}")

    elif args.wordpress_import_posts:
        if not ENABLE_WORDPRESS_SYNC:
            print("WordPress sync is not enabled. Set ENABLE_WORDPRESS_SYNC=true in .env")
            sys.exit(1)
        from tools.wordpress_sync import import_posts_from_wordpress
        result = asyncio.run(import_posts_from_wordpress(force_pull=args.force_pull))
        print(f"\nImported: {result['imported']} | Updated: {result['updated']} | Skipped: {result['skipped']}")

    elif args.wordpress_import_all:
        if not ENABLE_WORDPRESS_SYNC:
            print("WordPress sync is not enabled. Set ENABLE_WORDPRESS_SYNC=true in .env")
            sys.exit(1)
        from tools.wordpress_sync import import_all_from_wordpress
        result = asyncio.run(import_all_from_wordpress(force_pull=args.force_pull))
        print(f"\n=== WordPress Import Summary ===")
        print(f"Categories - Imported: {result['categories']['imported']} | Updated: {result['categories']['updated']} | Skipped: {result['categories']['skipped']}")
        print(f"Tags       - Imported: {result['tags']['imported']} | Updated: {result['tags']['updated']} | Skipped: {result['tags']['skipped']}")
        print(f"Posts      - Imported: {result['posts']['imported']} | Updated: {result['posts']['updated']} | Skipped: {result['posts']['skipped']}")

    elif args.autonomous:
        print(f"Autonomous Mode: Processing up to {args.count} idea(s) from queue")
        results = asyncio.run(process_idea_queue(count=args.count, verbose=args.verbose))

        # Summary
        print("\n" + "="*50)
        print("AUTONOMOUS MODE SUMMARY")
        print("="*50)
        successful = sum(1 for r in results if r["success"])
        print(f"Processed: {len(results)}")
        print(f"Successful: {successful}")
        print(f"Failed: {len(results) - successful}")

    elif args.backfill_images:
        print(f"Backfill Mode: Generating images for up to {args.count} post(s)")
        asyncio.run(backfill_images(count=args.count, verbose=args.verbose))

    elif args.backfill_images_all:
        print("Backfill Mode: Generating images for ALL posts without them")
        asyncio.run(backfill_images(count=1000, verbose=args.verbose))

    elif args.backfill_links:
        print(f"Backfill Mode: Adding links to up to {args.count} post(s)")
        asyncio.run(backfill_links(count=args.count, verbose=args.verbose))

    elif args.backfill_links_all:
        print("Backfill Mode: Adding links to ALL posts that need them")
        asyncio.run(backfill_links(count=1000, verbose=args.verbose))

    elif args.backfill_links_id:
        print(f"Backfill Mode: Adding links to post ID '{args.backfill_links_id}'")
        asyncio.run(backfill_links_single(post_id=args.backfill_links_id, verbose=args.verbose))

    elif args.backfill_links_slug:
        print(f"Backfill Mode: Adding links to post '{args.backfill_links_slug}'")
        asyncio.run(backfill_links_single(post_slug=args.backfill_links_slug, verbose=args.verbose))

    elif args.cleanup_links_all:
        print("Cleanup Mode: Removing internal links from ALL published posts")
        print("This will strip all internal <a> tags and preserve the anchor text.")
        confirm = input("Are you sure? Type 'yes' to continue: ")
        if confirm.lower() != 'yes':
            print("Cancelled.")
            sys.exit(0)
        from tools.link_tools import cleanup_internal_links
        results = asyncio.run(cleanup_internal_links(all_posts=True))
        total_removed = sum(r.get("removed", 0) for r in results if r.get("success"))
        print(f"\nCleaned {len(results)} posts, removed {total_removed} internal links")

    elif args.cleanup_links_id:
        from tools.link_tools import remove_internal_links_from_post
        print(f"Cleanup Mode: Removing internal links from post ID '{args.cleanup_links_id}'")
        result = asyncio.run(remove_internal_links_from_post(args.cleanup_links_id))
        if result.get("success"):
            print(f"Removed {result.get('removed', 0)} internal links from {result.get('post_slug', 'post')}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")

    elif args.cleanup_links:
        from tools.link_tools import cleanup_internal_links
        print(f"Cleanup Mode: Removing internal links from '{args.cleanup_links}'")
        results = asyncio.run(cleanup_internal_links(post_slugs=[args.cleanup_links]))
        if results and results[0].get("success"):
            print(f"Removed {results[0].get('removed', 0)} internal links")
        else:
            print(f"Error: {results[0].get('error', 'Unknown error')}")

    elif args.remove_link:
        from tools.link_tools import remove_single_link_by_id
        print(f"Cleanup Mode: Removing single link with ID '{args.remove_link}'")
        result = asyncio.run(remove_single_link_by_id(args.remove_link))
        if result.get("success"):
            print(f"Removed link from '{result.get('post_slug', 'post')}'")
            print(f"  URL: {result.get('url', 'N/A')}")
            print(f"  Anchor text: {result.get('anchor_text', 'N/A')}")
            print(f"  Link type: {result.get('link_type', 'N/A')}")
            if not result.get("removed_from_content"):
                print("  Note: Link record deleted but URL not found in post content")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")

    elif args.cleanup_image:
        from tools.image_tools import cleanup_post_image
        print(f"Cleanup Mode: Removing featured image from '{args.cleanup_image}'")
        result = asyncio.run(cleanup_post_image(post_slug=args.cleanup_image, verbose=args.verbose))
        if result.get("success"):
            print(f"Cleaned up image for '{result.get('post_slug')}'")
            print(f"Storage path: {result.get('storage_path')}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")

    elif args.cleanup_image_id:
        from tools.image_tools import cleanup_post_image
        print(f"Cleanup Mode: Removing featured image from post ID '{args.cleanup_image_id}'")
        result = asyncio.run(cleanup_post_image(post_id=args.cleanup_image_id, verbose=args.verbose))
        if result.get("success"):
            print(f"Cleaned up image for '{result.get('post_slug')}'")
            print(f"Storage path: {result.get('storage_path')}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")

    elif args.refresh_image:
        from tools.image_tools import refresh_post_image
        print(f"Refresh Mode: Replacing featured image for '{args.refresh_image}'")
        print("="*50)
        result = asyncio.run(refresh_post_image(post_slug=args.refresh_image, verbose=args.verbose))
        print("="*50)
        if result.get("success"):
            print(f"SUCCESS: New image for '{result.get('post_slug')}'")
            print(f"URL: {result.get('image_url')}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
            if result.get("cleanup_completed"):
                print("Note: Cleanup was completed, but image generation failed.")
                print("Run --backfill-images to generate a new image later.")

    elif args.refresh_image_id:
        from tools.image_tools import refresh_post_image
        print(f"Refresh Mode: Replacing featured image for post ID '{args.refresh_image_id}'")
        print("="*50)
        result = asyncio.run(refresh_post_image(post_id=args.refresh_image_id, verbose=args.verbose))
        print("="*50)
        if result.get("success"):
            print(f"SUCCESS: New image for '{result.get('post_slug')}'")
            print(f"URL: {result.get('image_url')}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
            if result.get("cleanup_completed"):
                print("Note: Cleanup was completed, but image generation failed.")
                print("Run --backfill-images to generate a new image later.")

    elif args.interactive:
        asyncio.run(interactive_mode(verbose=args.verbose))

    elif args.batch:
        asyncio.run(generate_batch(args.batch, verbose=args.verbose))

    elif args.topic:
        result = asyncio.run(generate_blog_post(args.topic, verbose=args.verbose))

        if result["success"]:
            print(f"\nBlog post created successfully!")
            print(f"Post ID: {result.get('post_id', 'check database')}")
            print(f"Turns used: {result.get('turns', 'unknown')}")
        else:
            print(f"\nFailed to generate blog post: {result.get('error', 'unknown error')}")
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
