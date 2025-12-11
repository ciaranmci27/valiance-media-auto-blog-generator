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


async def get_next_blog_idea(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get the next pending blog idea from the queue.

    Returns the highest priority pending idea, or indicates if the queue is empty.
    The idea is NOT automatically marked as in_progress - call claim_blog_idea after.
    """
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # Get the next pending idea by priority
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_ideas"
                f"?status=eq.pending"
                f"&select=id,topic,description,notes,target_category_slug,suggested_tags,target_word_count,priority,created_at"
                f"&order=priority.desc,created_at.asc"
                f"&limit=1",
                headers=headers
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Error fetching ideas (HTTP {resp.status}): {error}"
                        }],
                        "is_error": True
                    }

                ideas = await resp.json()

            if not ideas:
                return {
                    "content": [{
                        "type": "text",
                        "text": "No pending blog ideas in the queue. The queue is empty."
                    }]
                }

            idea = ideas[0]

            return {
                "content": [{
                    "type": "text",
                    "text": f"""Next blog idea found:

ID: {idea['id']}
Topic: {idea['topic']}
Priority: {idea['priority']}/100

Description: {idea.get('description') or 'No additional description'}

Notes: {idea.get('notes') or 'No notes'}

Target Category: {idea.get('target_category_slug') or 'Not specified - choose appropriate category'}

Suggested Tags: {', '.join(idea.get('suggested_tags') or []) or 'Not specified - choose relevant tags'}

Target Word Count: {idea.get('target_word_count') or '~1500 words'}

IMPORTANT: Call claim_blog_idea with this ID before starting to write the post."""
                }]
            }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error fetching next idea: {str(e)}"
            }],
            "is_error": True
        }


async def claim_blog_idea(args: dict[str, Any]) -> dict[str, Any]:
    """
    Mark an idea as 'in_progress' to claim it.

    This prevents other generator instances from picking up the same idea.
    Call this BEFORE starting to write the blog post.

    Args:
        idea_id: The UUID of the idea to claim
    """
    try:
        idea_id = args.get("idea_id")
        if not idea_id:
            return {
                "content": [{"type": "text", "text": "Missing required parameter: idea_id"}],
                "is_error": True
            }

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # Update the idea status
            async with session.patch(
                f"{SUPABASE_URL}/rest/v1/blog_ideas?id=eq.{idea_id}",
                headers=headers,
                json={
                    "status": "in_progress",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "attempts": 1  # Will be incremented on retries
                }
            ) as resp:
                if resp.status in [200, 204]:
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Successfully claimed idea {idea_id}. It is now marked as 'in_progress'. Proceed with generating the blog post."
                        }]
                    }
                else:
                    error = await resp.text()
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Failed to claim idea (HTTP {resp.status}): {error}"
                        }],
                        "is_error": True
                    }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error claiming idea: {str(e)}"
            }],
            "is_error": True
        }


async def complete_blog_idea(args: dict[str, Any]) -> dict[str, Any]:
    """
    Mark an idea as completed and link it to the created blog post.

    Call this AFTER successfully creating the blog post.

    Args:
        idea_id: The UUID of the idea
        blog_post_id: The UUID of the created blog post
    """
    try:
        idea_id = args.get("idea_id")
        blog_post_id = args.get("blog_post_id")

        if not idea_id or not blog_post_id:
            return {
                "content": [{"type": "text", "text": "Missing required parameters: idea_id and blog_post_id"}],
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
                    "error_message": None
                }
            ) as resp:
                if resp.status in [200, 204]:
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Blog idea {idea_id} marked as completed and linked to post {blog_post_id}."
                        }]
                    }
                else:
                    error = await resp.text()
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Failed to complete idea (HTTP {resp.status}): {error}"
                        }],
                        "is_error": True
                    }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error completing idea: {str(e)}"
            }],
            "is_error": True
        }


async def fail_blog_idea(args: dict[str, Any]) -> dict[str, Any]:
    """
    Mark an idea as failed with an error message.

    Use this if blog generation fails for any reason.
    Ideas can be retried later by resetting their status to 'pending'.

    Args:
        idea_id: The UUID of the idea
        error_message: Description of what went wrong
    """
    try:
        idea_id = args.get("idea_id")
        error_message = args.get("error_message", "Unknown error")

        if not idea_id:
            return {
                "content": [{"type": "text", "text": "Missing required parameter: idea_id"}],
                "is_error": True
            }

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # First get current attempt count
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_ideas?id=eq.{idea_id}&select=attempts",
                headers=headers
            ) as resp:
                ideas = await resp.json() if resp.status == 200 else []
                current_attempts = ideas[0].get("attempts", 0) if ideas else 0

            async with session.patch(
                f"{SUPABASE_URL}/rest/v1/blog_ideas?id=eq.{idea_id}",
                headers=headers,
                json={
                    "status": "failed",
                    "error_message": error_message,
                    "attempts": current_attempts + 1
                }
            ) as resp:
                if resp.status in [200, 204]:
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Blog idea {idea_id} marked as failed. Error: {error_message}"
                        }]
                    }
                else:
                    error = await resp.text()
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Failed to update idea (HTTP {resp.status}): {error}"
                        }],
                        "is_error": True
                    }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error marking idea as failed: {str(e)}"
            }],
            "is_error": True
        }


async def skip_blog_idea(args: dict[str, Any]) -> dict[str, Any]:
    """
    Skip an idea without generating a post.

    Use this if the idea is a duplicate, not appropriate, or should be handled differently.

    Args:
        idea_id: The UUID of the idea
        reason: Why this idea is being skipped
    """
    try:
        idea_id = args.get("idea_id")
        reason = args.get("reason", "Skipped by generator")

        if not idea_id:
            return {
                "content": [{"type": "text", "text": "Missing required parameter: idea_id"}],
                "is_error": True
            }

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            async with session.patch(
                f"{SUPABASE_URL}/rest/v1/blog_ideas?id=eq.{idea_id}",
                headers=headers,
                json={
                    "status": "skipped",
                    "error_message": f"Skipped: {reason}",
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }
            ) as resp:
                if resp.status in [200, 204]:
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Blog idea {idea_id} skipped. Reason: {reason}"
                        }]
                    }
                else:
                    error = await resp.text()
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Failed to skip idea (HTTP {resp.status}): {error}"
                        }],
                        "is_error": True
                    }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error skipping idea: {str(e)}"
            }],
            "is_error": True
        }


async def get_idea_queue_status(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get a summary of the blog ideas queue.

    Returns counts by status and the next few pending ideas.
    """
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # Get counts by status
            counts = {}
            for status in ["pending", "in_progress", "completed", "failed", "skipped"]:
                async with session.get(
                    f"{SUPABASE_URL}/rest/v1/blog_ideas?status=eq.{status}&select=id",
                    headers={**headers, "Prefer": "count=exact"}
                ) as resp:
                    # Get count from content-range header
                    content_range = resp.headers.get("content-range", "")
                    if "/" in content_range:
                        counts[status] = int(content_range.split("/")[1])
                    else:
                        data = await resp.json()
                        counts[status] = len(data) if resp.status == 200 else 0

            # Get next 5 pending ideas
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_ideas"
                f"?status=eq.pending"
                f"&select=topic,priority"
                f"&order=priority.desc,created_at.asc"
                f"&limit=5",
                headers=headers
            ) as resp:
                upcoming = await resp.json() if resp.status == 200 else []

            summary = f"""Blog Ideas Queue Status:

Pending: {counts.get('pending', 0)}
In Progress: {counts.get('in_progress', 0)}
Completed: {counts.get('completed', 0)}
Failed: {counts.get('failed', 0)}
Skipped: {counts.get('skipped', 0)}

Next up (by priority):"""

            for i, idea in enumerate(upcoming, 1):
                summary += f"\n  {i}. [{idea['priority']}] {idea['topic']}"

            if not upcoming:
                summary += "\n  (queue is empty)"

            return {
                "content": [{
                    "type": "text",
                    "text": summary
                }]
            }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error getting queue status: {str(e)}"
            }],
            "is_error": True
        }


# Tool definitions for Claude Agent SDK
IDEA_TOOLS = [
    {
        "name": "get_next_blog_idea",
        "description": """Get the next pending blog idea from the queue.

Returns the highest priority idea that hasn't been processed yet.
After getting an idea, call claim_blog_idea to mark it as in_progress before writing.

Returns: The idea with topic, description, notes, and any targeting hints.""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "function": get_next_blog_idea
    },
    {
        "name": "claim_blog_idea",
        "description": """Mark an idea as 'in_progress' to claim it before writing.

ALWAYS call this after get_next_blog_idea and BEFORE starting to write the post.
This prevents duplicate processing if multiple generators are running.

Args:
    idea_id: The UUID from get_next_blog_idea""",
        "input_schema": {
            "type": "object",
            "properties": {
                "idea_id": {
                    "type": "string",
                    "description": "The UUID of the idea to claim"
                }
            },
            "required": ["idea_id"]
        },
        "function": claim_blog_idea
    },
    {
        "name": "complete_blog_idea",
        "description": """Mark an idea as completed and link it to the created post.

Call this AFTER successfully creating the blog post and linking tags.

Args:
    idea_id: The UUID of the idea
    blog_post_id: The UUID of the created blog post""",
        "input_schema": {
            "type": "object",
            "properties": {
                "idea_id": {
                    "type": "string",
                    "description": "The UUID of the idea"
                },
                "blog_post_id": {
                    "type": "string",
                    "description": "The UUID of the created blog post"
                }
            },
            "required": ["idea_id", "blog_post_id"]
        },
        "function": complete_blog_idea
    },
    {
        "name": "fail_blog_idea",
        "description": """Mark an idea as failed if generation encounters an error.

Use this if you cannot complete the blog post for any reason.
The idea can be retried later by resetting its status.

Args:
    idea_id: The UUID of the idea
    error_message: What went wrong""",
        "input_schema": {
            "type": "object",
            "properties": {
                "idea_id": {
                    "type": "string",
                    "description": "The UUID of the idea"
                },
                "error_message": {
                    "type": "string",
                    "description": "Description of what went wrong"
                }
            },
            "required": ["idea_id", "error_message"]
        },
        "function": fail_blog_idea
    },
    {
        "name": "skip_blog_idea",
        "description": """Skip an idea without generating a post.

Use when:
- The topic is too similar to an existing post
- The topic isn't appropriate for the blog
- More information/clarification is needed

Args:
    idea_id: The UUID of the idea
    reason: Why skipping this idea""",
        "input_schema": {
            "type": "object",
            "properties": {
                "idea_id": {
                    "type": "string",
                    "description": "The UUID of the idea"
                },
                "reason": {
                    "type": "string",
                    "description": "Why this idea is being skipped"
                }
            },
            "required": ["idea_id", "reason"]
        },
        "function": skip_blog_idea
    },
    {
        "name": "get_idea_queue_status",
        "description": """Get a summary of the blog ideas queue.

Shows counts by status and the next few pending ideas.
Useful for understanding the current state of the queue.""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "function": get_idea_queue_status
    }
]
