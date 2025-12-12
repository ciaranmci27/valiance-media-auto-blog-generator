"""
Write Tools - Create and update operations for blog content

These tools allow Claude to create new blog posts, categories, tags,
and manage relationships between them.
"""

import json
from typing import Any
import aiohttp
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SUPABASE_URL, get_supabase_headers, DEFAULT_STATUS


async def create_blog_post(args: dict[str, Any]) -> dict[str, Any]:
    """Create a new blog post in Supabase. Optionally links tags in same call."""
    try:
        # Build the post data
        post_data = {
            "slug": args["slug"],
            "title": args["title"],
            "excerpt": args["excerpt"],
            "content": args["content"],
            "author_id": args["author_id"],
            "status": args.get("status", DEFAULT_STATUS),
            "featured": args.get("featured", False),
        }

        # Optional fields
        if args.get("category_id"):
            post_data["category_id"] = args["category_id"]
        if args.get("featured_image"):
            post_data["featured_image"] = args["featured_image"]
        if args.get("featured_image_alt"):
            post_data["featured_image_alt"] = args["featured_image_alt"]
        if args.get("reading_time"):
            post_data["reading_time"] = args["reading_time"]
        else:
            content_text = json.dumps(args["content"])
            post_data["reading_time"] = max(1, len(content_text.split()) // 200)
        if args.get("seo"):
            post_data["seo"] = args["seo"]
        if args.get("scheduled_at"):
            post_data["scheduled_at"] = args["scheduled_at"]

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            async with session.post(
                f"{SUPABASE_URL}/rest/v1/blog_posts",
                headers=headers,
                json=post_data
            ) as resp:
                if resp.status not in [200, 201]:
                    error = await resp.text()
                    return {"content": [{"type": "text", "text": f"Error: {error}"}], "is_error": True}

                result = await resp.json()
                created_post = result[0] if isinstance(result, list) else result
                post_id = created_post['id']

            # Link tags if provided (saves a separate tool call)
            tag_ids = args.get("tag_ids", [])
            tags_linked = 0
            if tag_ids:
                links = [{"post_id": post_id, "tag_id": tag_id} for tag_id in tag_ids]
                async with session.post(
                    f"{SUPABASE_URL}/rest/v1/blog_post_tags",
                    headers=headers,
                    json=links
                ) as resp:
                    if resp.status in [200, 201]:
                        tags_linked = len(tag_ids)

            return {
                "content": [{
                    "type": "text",
                    "text": f"Created: {post_id} ({created_post['slug']})" + (f" +{tags_linked} tags" if tags_linked else "")
                }]
            }

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


async def create_category(args: dict[str, Any]) -> dict[str, Any]:
    """Create a new blog category. Prefer using existing categories."""
    try:
        category_data = {"slug": args["slug"], "name": args["name"]}
        if args.get("description"):
            category_data["description"] = args["description"]
        if args.get("seo"):
            category_data["seo"] = args["seo"]

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.post(
                f"{SUPABASE_URL}/rest/v1/blog_categories",
                headers=headers,
                json=category_data
            ) as resp:
                if resp.status in [200, 201]:
                    result = await resp.json()
                    created = result[0] if isinstance(result, list) else result
                    return {"content": [{"type": "text", "text": f"Created category: {created['id']} ({created['slug']})"}]}
                else:
                    error = await resp.text()
                    return {"content": [{"type": "text", "text": f"Error: {error}"}], "is_error": True}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


async def create_tag(args: dict[str, Any]) -> dict[str, Any]:
    """Create a new blog tag. Check existing tags first to avoid duplicates."""
    try:
        tag_data = {"slug": args["slug"], "name": args["name"]}

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.post(
                f"{SUPABASE_URL}/rest/v1/blog_tags",
                headers=headers,
                json=tag_data
            ) as resp:
                if resp.status in [200, 201]:
                    result = await resp.json()
                    created = result[0] if isinstance(result, list) else result
                    return {"content": [{"type": "text", "text": f"Created tag: {created['id']} ({created['slug']})"}]}
                else:
                    error = await resp.text()
                    return {"content": [{"type": "text", "text": f"Error: {error}"}], "is_error": True}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


async def link_tags_to_post(args: dict[str, Any]) -> dict[str, Any]:
    """Link tags to an existing post. Prefer passing tag_ids to create_blog_post instead."""
    try:
        post_id = args["post_id"]
        tag_ids = args["tag_ids"]

        if not tag_ids:
            return {"content": [{"type": "text", "text": "No tags provided"}]}

        links = [{"post_id": post_id, "tag_id": tag_id} for tag_id in tag_ids]

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.post(
                f"{SUPABASE_URL}/rest/v1/blog_post_tags",
                headers=headers,
                json=links
            ) as resp:
                if resp.status in [200, 201]:
                    return {"content": [{"type": "text", "text": f"Linked {len(tag_ids)} tags"}]}
                else:
                    error = await resp.text()
                    return {"content": [{"type": "text", "text": f"Error: {error}"}], "is_error": True}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


async def update_post_status(args: dict[str, Any]) -> dict[str, Any]:
    """Update post status (draft/published/archived)."""
    try:
        post_id = args["post_id"]
        status = args["status"]

        if status not in ["draft", "published", "scheduled", "archived"]:
            return {"content": [{"type": "text", "text": f"Invalid status: {status}"}], "is_error": True}

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.patch(
                f"{SUPABASE_URL}/rest/v1/blog_posts?id=eq.{post_id}",
                headers=headers,
                json={"status": status}
            ) as resp:
                if resp.status in [200, 204]:
                    return {"content": [{"type": "text", "text": f"Updated: {post_id} → {status}"}]}
                else:
                    error = await resp.text()
                    return {"content": [{"type": "text", "text": f"Error: {error}"}], "is_error": True}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


async def update_post_image(post_id: str, image_url: str, alt_text: str = None) -> bool:
    """Update a post's featured image (for backfill). Returns True on success."""
    try:
        update_data = {"featured_image": image_url}
        if alt_text:
            update_data["featured_image_alt"] = alt_text

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.patch(
                f"{SUPABASE_URL}/rest/v1/blog_posts?id=eq.{post_id}",
                headers=headers,
                json=update_data
            ) as resp:
                return resp.status in [200, 204]
    except Exception:
        return False


# Tool definitions for Claude Agent SDK
WRITE_TOOLS = [
    {
        "name": "create_blog_post",
        "description": "Create a blog post. Content is array of blocks [{id, type, data}]. Pass tag_ids to link tags in same call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "URL slug (lowercase, hyphens)"},
                "title": {"type": "string", "description": "Post title"},
                "excerpt": {"type": "string", "description": "Short description (2-3 sentences)"},
                "content": {
                    "type": "array",
                    "description": "Array of content blocks",
                    "items": {"type": "object", "required": ["id", "type", "data"]}
                },
                "author_id": {"type": "string", "description": "Author UUID from get_blog_context"},
                "category_id": {"type": "string", "description": "Category UUID (optional)"},
                "tag_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tag UUIDs to link (optional, saves a tool call)"
                },
                "featured_image": {"type": "string", "description": "Image URL (optional)"},
                "featured_image_alt": {"type": "string", "description": "Image alt text"},
                "seo": {"type": "object", "description": "{title, description, keywords[]}"},
                "status": {"type": "string", "enum": ["draft", "published", "scheduled", "archived"]},
                "scheduled_at": {"type": "string", "description": "ISO timestamp for scheduled publish (required if status=scheduled)"}
            },
            "required": ["slug", "title", "excerpt", "content", "author_id"]
        },
        "function": create_blog_post
    },
    {
        "name": "create_category",
        "description": "Create new category. Use existing categories when possible.",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "URL slug"},
                "name": {"type": "string", "description": "Display name"},
                "description": {"type": "string", "description": "Category description"}
            },
            "required": ["slug", "name"]
        },
        "function": create_category
    },
    {
        "name": "create_tag",
        "description": "Create new tag. Check existing tags first to avoid duplicates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "URL slug"},
                "name": {"type": "string", "description": "Display name"}
            },
            "required": ["slug", "name"]
        },
        "function": create_tag
    },
    {
        "name": "link_tags_to_post",
        "description": "Link tags to existing post. Prefer passing tag_ids to create_blog_post.",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "string", "description": "Post UUID"},
                "tag_ids": {"type": "array", "items": {"type": "string"}, "description": "Tag UUIDs"}
            },
            "required": ["post_id", "tag_ids"]
        },
        "function": link_tags_to_post
    },
    {
        "name": "update_post_status",
        "description": "Update post status (draft/published/scheduled/archived).",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "string", "description": "Post UUID"},
                "status": {"type": "string", "enum": ["draft", "published", "scheduled", "archived"]}
            },
            "required": ["post_id", "status"]
        },
        "function": update_post_status
    }
]
