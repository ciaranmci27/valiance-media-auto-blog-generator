"""
Query Tools - Read operations for blog context

These tools allow Claude to understand what already exists in the database
before generating new content.
"""

import json
from typing import Any
import aiohttp
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SUPABASE_URL, get_supabase_headers


async def get_blog_context(args: dict[str, Any]) -> dict[str, Any]:
    """Get categories, tags, authors, and recent post slugs. Call first before creating content."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # Fetch categories (id, slug, name only - skip description to save tokens)
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_categories?select=id,slug,name&order=sort_order",
                headers=headers
            ) as resp:
                categories = await resp.json() if resp.status == 200 else []

            # Fetch tags (id, slug, name)
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_tags?select=id,slug,name&order=name",
                headers=headers
            ) as resp:
                tags = await resp.json() if resp.status == 200 else []

            # Fetch authors (id, slug, name only - skip bio to save tokens)
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_authors?select=id,slug,name",
                headers=headers
            ) as resp:
                authors = await resp.json() if resp.status == 200 else []

            # Fetch recent post slugs only (reduced from 50 to 20, skip titles)
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?select=slug&order=created_at.desc&limit=20",
                headers=headers
            ) as resp:
                recent = await resp.json() if resp.status == 200 else []

            # Compact format to save tokens
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "categories": categories,
                        "tags": tags,
                        "authors": authors,
                        "recent_slugs": [p["slug"] for p in recent]
                    }, separators=(',', ':'))
                }]
            }

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


async def get_sample_post(args: dict[str, Any]) -> dict[str, Any]:
    """Get a sample published post to see content block structure."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            query = f"{SUPABASE_URL}/rest/v1/blog_posts?select=content&status=eq.published&limit=1"

            if args.get("category_slug"):
                async with session.get(
                    f"{SUPABASE_URL}/rest/v1/blog_categories?select=id&slug=eq.{args['category_slug']}&limit=1",
                    headers=headers
                ) as resp:
                    cats = await resp.json() if resp.status == 200 else []
                    if cats:
                        query += f"&category_id=eq.{cats[0]['id']}"

            async with session.get(query, headers=headers) as resp:
                posts = await resp.json() if resp.status == 200 else []

            if not posts:
                return {"content": [{"type": "text", "text": "No published posts found"}]}

            # Return just the content blocks (most useful part)
            return {"content": [{"type": "text", "text": json.dumps(posts[0].get("content", []), separators=(',', ':'))}]}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


async def check_slug_exists(args: dict[str, Any]) -> dict[str, Any]:
    """Check if a slug exists in posts/categories/tags."""
    try:
        slug = args.get("slug", "")
        table = args.get("table", "posts")
        table_map = {"posts": "blog_posts", "categories": "blog_categories", "tags": "blog_tags"}
        db_table = table_map.get(table, "blog_posts")

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/{db_table}?select=slug&slug=eq.{slug}",
                headers=headers
            ) as resp:
                results = await resp.json() if resp.status == 200 else []

            exists = len(results) > 0
            return {"content": [{"type": "text", "text": f"{slug}: {'EXISTS' if exists else 'available'}"}]}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


async def get_posts_without_images(limit: int = 10) -> list:
    """Get posts that don't have featured images (for backfill)."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            # Get posts where featured_image is null, include category for prompt context
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?select=id,slug,title,excerpt,category_id,blog_categories(slug)&featured_image=is.null&order=created_at.desc&limit={limit}",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return []
    except Exception:
        return []


# Tool definitions for Claude Agent SDK
QUERY_TOOLS = [
    {
        "name": "get_blog_context",
        "description": "Get all categories, tags, authors, and recent post slugs. Call FIRST before creating content.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "function": get_blog_context
    },
    {
        "name": "get_sample_post",
        "description": "Get sample post content blocks to see structure.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category_slug": {"type": "string", "description": "Optional: filter by category"}
            },
            "required": []
        },
        "function": get_sample_post
    },
    {
        "name": "check_slug_exists",
        "description": "Check if slug exists in posts/categories/tags.",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug to check"},
                "table": {"type": "string", "enum": ["posts", "categories", "tags"]}
            },
            "required": ["slug", "table"]
        },
        "function": check_slug_exists
    }
]
