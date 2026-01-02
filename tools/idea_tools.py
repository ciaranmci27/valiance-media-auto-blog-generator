"""
Idea Management Tools - Queue-based autonomous blog generation

These tools allow Claude to work through a queue of blog ideas,
picking up the next idea and marking them as complete.
"""

import json
from typing import Any
import aiohttp
import sys
import os
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SUPABASE_URL, get_supabase_headers


async def get_and_claim_blog_idea(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get the next pending blog idea and atomically claim it.
    Combines fetch + claim into one operation to save a turn.
    """
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # Get the next pending idea by priority (simplified schema)
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_ideas"
                f"?status=eq.pending"
                f"&select=id,topic,description,notes,priority"
                f"&order=priority.desc.nullslast,created_at.asc"
                f"&limit=1",
                headers=headers
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    return {
                        "content": [{"type": "text", "text": f"Error: {error}"}],
                        "is_error": True
                    }
                ideas = await resp.json()

            if not ideas:
                return {
                    "content": [{"type": "text", "text": "Queue empty. No pending ideas."}]
                }

            idea = ideas[0]
            idea_id = idea['id']

            # Immediately claim it
            async with session.patch(
                f"{SUPABASE_URL}/rest/v1/blog_ideas?id=eq.{idea_id}",
                headers=headers,
                json={
                    "status": "in_progress",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "attempts": 1
                }
            ) as resp:
                if resp.status not in [200, 204]:
                    error = await resp.text()
                    return {
                        "content": [{"type": "text", "text": f"Failed to claim: {error}"}],
                        "is_error": True
                    }

            # Build concise response - only include description/notes if populated
            response_lines = [
                f"ID: {idea_id}",
                f"Topic: {idea['topic']}"
            ]

            # Only add description/notes if they have actual content (not null/empty)
            description = idea.get('description')
            if description and description.strip():
                response_lines.append(f"Description: {description}")

            notes = idea.get('notes')
            if notes and notes.strip():
                response_lines.append(f"Notes: {notes}")

            response_lines.append("Status: CLAIMED")

            return {
                "content": [{
                    "type": "text",
                    "text": "\n".join(response_lines)
                }]
            }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "is_error": True
        }


async def complete_blog_idea(args: dict[str, Any]) -> dict[str, Any]:
    """Mark an idea as completed and link it to the created blog post."""
    try:
        idea_id = args.get("idea_id")
        blog_post_id = args.get("blog_post_id")

        if not idea_id or not blog_post_id:
            return {
                "content": [{"type": "text", "text": "Missing: idea_id and blog_post_id"}],
                "is_error": True
            }

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.patch(
                f"{SUPABASE_URL}/rest/v1/blog_ideas?id=eq.{idea_id}",
                headers=headers,
                json={
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "blog_post_id": blog_post_id,
                    "error_message": None,
                    "priority": None
                }
            ) as resp:
                if resp.status in [200, 204]:
                    return {"content": [{"type": "text", "text": f"Completed: {idea_id} → {blog_post_id}"}]}
                else:
                    error = await resp.text()
                    return {"content": [{"type": "text", "text": f"Error: {error}"}], "is_error": True}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


async def fail_blog_idea(args: dict[str, Any]) -> dict[str, Any]:
    """Mark an idea as failed with an error message."""
    try:
        idea_id = args.get("idea_id")
        error_message = args.get("error_message", "Unknown error")

        if not idea_id:
            return {"content": [{"type": "text", "text": "Missing: idea_id"}], "is_error": True}

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            async with session.patch(
                f"{SUPABASE_URL}/rest/v1/blog_ideas?id=eq.{idea_id}",
                headers=headers,
                json={"status": "failed", "error_message": error_message, "priority": None}
            ) as resp:
                if resp.status in [200, 204]:
                    return {"content": [{"type": "text", "text": f"Failed: {idea_id} - {error_message}"}]}
                else:
                    error = await resp.text()
                    return {"content": [{"type": "text", "text": f"Error: {error}"}], "is_error": True}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


async def skip_blog_idea(args: dict[str, Any]) -> dict[str, Any]:
    """Skip an idea without generating a post."""
    try:
        idea_id = args.get("idea_id")
        reason = args.get("reason", "Skipped")

        if not idea_id:
            return {"content": [{"type": "text", "text": "Missing: idea_id"}], "is_error": True}

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.patch(
                f"{SUPABASE_URL}/rest/v1/blog_ideas?id=eq.{idea_id}",
                headers=headers,
                json={
                    "status": "skipped",
                    "error_message": reason,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "priority": None
                }
            ) as resp:
                if resp.status in [200, 204]:
                    return {"content": [{"type": "text", "text": f"Skipped: {idea_id} - {reason}"}]}
                else:
                    error = await resp.text()
                    return {"content": [{"type": "text", "text": f"Error: {error}"}], "is_error": True}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


async def get_pending_idea_count() -> tuple[int, str | None]:
    """
    Get the count of pending ideas in the queue.

    This is a lightweight pre-flight check that doesn't invoke the AI agent.
    Used to determine if there are enough ideas before starting autonomous mode.

    Returns:
        Tuple of (count, error_message). Error is None on success.
    """
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # Use Supabase's count feature with limit=0 for efficiency (no row data returned)
            count_headers = {**headers, "Prefer": "count=exact"}
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_ideas?status=eq.pending&select=id&limit=0",
                headers=count_headers
            ) as resp:
                if resp.status == 200:
                    # Supabase returns count in content-range header
                    # Format: "0-0/total" or "*/total" if no results
                    content_range = resp.headers.get("content-range", "")
                    if "/" in content_range:
                        total = content_range.split("/")[-1]
                        if total and total != "*":
                            return int(total), None
                        # total is empty or "*" - means 0 results
                        return 0, None

                    # Header missing or malformed - treat as error, not as 0 count
                    # This avoids silently skipping runs when Supabase is misconfigured
                    return 0, "Content-range header missing from Supabase response"

                # Non-200 response
                error_text = await resp.text()
                return 0, f"Failed to check queue: HTTP {resp.status} - {error_text[:100]}"

    except Exception as e:
        return 0, f"Failed to check queue: {str(e)}"


async def get_idea_queue_status(args: dict[str, Any]) -> dict[str, Any]:
    """Get queue status counts."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # Get counts by status in one query
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_ideas?select=status",
                headers=headers
            ) as resp:
                ideas = await resp.json() if resp.status == 200 else []

            counts = {"pending": 0, "in_progress": 0, "completed": 0, "failed": 0, "skipped": 0}
            for idea in ideas:
                status = idea.get("status", "pending")
                if status in counts:
                    counts[status] += 1

            return {
                "content": [{
                    "type": "text",
                    "text": f"Queue: {counts['pending']} pending, {counts['in_progress']} active, {counts['completed']} done, {counts['failed']} failed"
                }]
            }

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


# Tool definitions for Claude Agent SDK
IDEA_TOOLS = [
    {
        "name": "get_and_claim_blog_idea",
        "description": "Get next pending idea and claim it atomically. Returns ID, topic, and optional description/notes (only if populated). Call this first in autonomous mode.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "function": get_and_claim_blog_idea
    },
    {
        "name": "complete_blog_idea",
        "description": "Mark idea as completed after creating the blog post.",
        "input_schema": {
            "type": "object",
            "properties": {
                "idea_id": {"type": "string", "description": "The idea UUID"},
                "blog_post_id": {"type": "string", "description": "The created post UUID"}
            },
            "required": ["idea_id", "blog_post_id"]
        },
        "function": complete_blog_idea
    },
    {
        "name": "fail_blog_idea",
        "description": "Mark idea as failed if generation errors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "idea_id": {"type": "string", "description": "The idea UUID"},
                "error_message": {"type": "string", "description": "What went wrong"}
            },
            "required": ["idea_id", "error_message"]
        },
        "function": fail_blog_idea
    },
    {
        "name": "skip_blog_idea",
        "description": "Skip idea without generating (duplicate topic, inappropriate, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "idea_id": {"type": "string", "description": "The idea UUID"},
                "reason": {"type": "string", "description": "Why skipping"}
            },
            "required": ["idea_id", "reason"]
        },
        "function": skip_blog_idea
    },
    {
        "name": "get_idea_queue_status",
        "description": "Get queue counts by status.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "function": get_idea_queue_status
    }
]
