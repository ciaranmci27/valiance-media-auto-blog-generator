#!/usr/bin/env python3
"""
Autonomous Blog Generator

This script uses Claude to autonomously generate blog posts.
It can operate in several modes:
1. Manual mode: Generate a post about a specific topic
2. Autonomous mode: Process posts from a queue of blog ideas
3. Backfill mode: Generate images for posts missing them

Usage:
    python generator.py "topic to write about"          # Manual mode
    python generator.py --autonomous                    # Process ideas from queue
    python generator.py --autonomous --count 5          # Process up to 5 ideas
    python generator.py --backfill-images               # Generate missing images
    python generator.py --backfill-images --count 10    # Backfill up to 10 images
    python generator.py --batch topics.txt              # Batch from file
    python generator.py --interactive                   # Interactive mode
    python generator.py --status                        # Show queue status

Examples:
    python generator.py "How to fix a slice"
    python generator.py --autonomous --verbose
    python generator.py --backfill-images --count 5
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
    ENABLE_IMAGE_GENERATION,
    BLOGS_PER_RUN,
)
from tools.query_tools import QUERY_TOOLS
from tools.write_tools import WRITE_TOOLS
from tools.idea_tools import IDEA_TOOLS
from tools.image_tools import IMAGE_TOOLS


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

    if errors:
        return {"success": False, "errors": errors}

    if verbose:
        print("✓ Health check passed\n")

    return {"success": True, "errors": []}


def load_system_prompt() -> str:
    """Load the system prompt from file"""
    prompt_path = Path(__file__).parent / "prompts" / "system_prompt.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


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
    return tools


async def execute_tool(tool_name: str, tool_input: dict, include_idea_tools: bool = True) -> dict:
    """Execute a tool by name and return the result"""
    all_tools = get_all_tools(include_idea_tools)

    for tool in all_tools:
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
    include_idea_tools: bool = True
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
    system_prompt = load_system_prompt()

    # Build tool definitions for API
    tools = []
    for tool in get_all_tools(include_idea_tools, verbose=verbose):
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

                        result = await execute_tool(tool_name, tool_input, include_idea_tools)

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

The default author slug is: {DEFAULT_AUTHOR_SLUG}
Posts should be created as 'draft' status for review.

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

    for i in range(count):
        print(f"\n{'='*50}")
        print(f"Processing idea {i+1}/{count}")
        print("="*50)

        initial_message = f"""You are in AUTONOMOUS MODE. Process the next blog idea from the queue.

Workflow:
1. Call get_and_claim_blog_idea to get and claim the next pending idea
2. If the queue is empty, respond that there are no ideas to process
3. Call get_blog_context to understand existing content
4. Generate the blog post based on the idea's topic, description, and notes
5. Use the targeting hints (category, tags) if provided, or choose appropriate ones
6. Create the post with create_blog_post (pass tag_ids to link tags in same call)
7. Call complete_blog_idea with the idea_id and blog_post_id

If anything fails, call fail_blog_idea with the error message.
If the idea should be skipped (duplicate, inappropriate), call skip_blog_idea with reason.

The default author slug is: {DEFAULT_AUTHOR_SLUG}
Posts should be created as 'draft' status for review.

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


def _create_scene_prompt(title: str, excerpt: str = "") -> str:
    """
    Create a scene-based image prompt from a blog title.

    Avoids words like "article", "blog", "guide" that cause Gemini to render text.
    Instead focuses on describing a visual scene related to the topic.
    """
    # Remove common article-type words that shouldn't appear in image prompts
    cleanup_words = [
        "complete guide", "guide to", "how to", "what is", "what are",
        "explained", "tips", "tricks", "best", "top", "ultimate",
        ": complete", "- complete", "for beginners", "for experts",
    ]

    scene_base = title.lower()
    for word in cleanup_words:
        scene_base = scene_base.replace(word.lower(), "")

    # Clean up extra spaces and punctuation
    scene_base = " ".join(scene_base.split()).strip(" :-")

    # Build a scene description
    if scene_base:
        prompt = f"A beautiful photograph depicting {scene_base}, cinematic composition, hero image style"
    else:
        # Fallback to excerpt if title cleanup removed everything
        prompt = f"A beautiful photograph related to: {excerpt[:150]}, cinematic composition"

    return prompt


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

        # Create scene-based prompt (avoid mentioning "article" or "blog" to prevent text rendering)
        # Extract the core subject from the title and describe a visual scene
        prompt = _create_scene_prompt(title, excerpt)

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
                # Update the post
                alt_text = f"Featured image for {title}"
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
    print("ClutchCaddie Blog Generator - Interactive Mode")
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
  MANUAL:      python generator.py "How to fix your slice"
  AUTONOMOUS:  python generator.py --autonomous
  BACKFILL:    python generator.py --backfill-images
  BATCH:       python generator.py --batch topics.txt
  INTERACTIVE: python generator.py --interactive
  STATUS:      python generator.py --status

Examples:
  # Generate one post about a specific topic
  python generator.py "Best putting drills for beginners" --verbose

  # Process the next idea from the queue
  python generator.py --autonomous

  # Process up to 5 ideas from the queue
  python generator.py --autonomous --count 5

  # Generate images for posts missing them
  python generator.py --backfill-images --count 10

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
        help="Generate images for posts that don't have them"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed progress"
    )

    args = parser.parse_args()

    # Validate configuration
    try:
        validate_config()
    except ValueError as e:
        print(f"Configuration Error: {e}")
        sys.exit(1)

    # Health check (skip for status-only commands)
    if not args.status:
        health = asyncio.run(health_check(verbose=args.verbose))
        if not health["success"]:
            print("Health check failed:")
            for error in health["errors"]:
                print(f"  ✗ {error}")
            sys.exit(1)

    # Run appropriate mode
    if args.status:
        asyncio.run(get_queue_status())

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
