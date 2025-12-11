#!/usr/bin/env python3
"""
ClutchCaddie Autonomous Blog Generator

This script uses Claude to autonomously generate blog posts for ClutchCaddie.
It can operate in two modes:
1. Manual mode: Generate a post about a specific topic
2. Autonomous mode: Process posts from a queue of blog ideas

Usage:
    python generator.py "topic to write about"          # Manual mode
    python generator.py --autonomous                    # Process one idea from queue
    python generator.py --autonomous --count 5          # Process up to 5 ideas
    python generator.py --batch topics.txt              # Batch from file
    python generator.py --interactive                   # Interactive mode
    python generator.py --status                        # Show queue status

Examples:
    python generator.py "How to fix a slice"
    python generator.py --autonomous --verbose
    python generator.py --autonomous --count 3
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
)
from tools.query_tools import QUERY_TOOLS
from tools.write_tools import WRITE_TOOLS
from tools.idea_tools import IDEA_TOOLS


def load_system_prompt() -> str:
    """Load the system prompt from file"""
    prompt_path = Path(__file__).parent / "prompts" / "system_prompt.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def get_all_tools(include_idea_tools: bool = True) -> list:
    """Combine all tool definitions"""
    tools = QUERY_TOOLS + WRITE_TOOLS
    if include_idea_tools:
        tools = tools + IDEA_TOOLS
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
    for tool in get_all_tools(include_idea_tools):
        tools.append({
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": tool["input_schema"]
        })

    messages = [{"role": "user", "content": initial_message}]

    turn_count = 0
    created_post_id = None
    idea_id = None

    while turn_count < MAX_TURNS:
        turn_count += 1

        if verbose:
            print(f"\n--- Turn {turn_count}/{MAX_TURNS} ---")

        # Call Claude
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=16384,
            system=system_prompt,
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
                        if "Post ID:" in result_text:
                            for line in result_text.split("\n"):
                                if "Post ID:" in line:
                                    created_post_id = line.split("Post ID:")[1].strip()
                                    break

                    if tool_name == "claim_blog_idea" and not is_error:
                        idea_id = tool_input.get("idea_id")

                    if tool_name == "get_next_blog_idea" and "ID:" in result_text:
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

    return {
        "success": False,
        "error": f"Max turns ({MAX_TURNS}) reached without completion",
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
4. Create a high-quality, SEO-optimized blog post using create_blog_post
5. Link relevant tags to the post using link_tags_to_post

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
1. Call get_next_blog_idea to get the next pending idea
2. If the queue is empty, respond that there are no ideas to process
3. If an idea is found, call claim_blog_idea with the idea_id
4. Call get_blog_context to understand existing content
5. Generate the blog post based on the idea's topic, description, and notes
6. Use the targeting hints (category, tags) if provided, or choose appropriate ones
7. Create the post with create_blog_post
8. Link relevant tags with link_tags_to_post
9. Call complete_blog_idea with the idea_id and blog_post_id

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
        description="Generate blog posts for ClutchCaddie using Claude AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  MANUAL:      python generator.py "How to fix your slice"
  AUTONOMOUS:  python generator.py --autonomous
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
        default=1,
        help="Number of ideas to process in autonomous mode (default: 1)"
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
