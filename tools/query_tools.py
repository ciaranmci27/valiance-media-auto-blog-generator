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
    """
    Get complete blog context including all categories, tags, and authors.
    This should be called FIRST before generating any content.

    Returns:
        - All existing categories (id, slug, name, description)
        - All existing tags (id, slug, name)
        - All authors (id, slug, name, bio)
        - Recent post titles (to avoid duplicates)
    """
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # Fetch categories
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_categories?select=id,slug,name,description&order=sort_order",
                headers=headers
            ) as resp:
                categories = await resp.json() if resp.status == 200 else []

            # Fetch tags
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_tags?select=id,slug,name&order=name",
                headers=headers
            ) as resp:
                tags = await resp.json() if resp.status == 200 else []

            # Fetch authors
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_authors?select=id,slug,name,bio",
                headers=headers
            ) as resp:
                authors = await resp.json() if resp.status == 200 else []

            # Fetch recent post titles/slugs to avoid duplicates
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?select=slug,title&order=created_at.desc&limit=50",
                headers=headers
            ) as resp:
                recent_posts = await resp.json() if resp.status == 200 else []

            context = {
                "categories": categories,
                "tags": tags,
                "authors": authors,
                "recent_posts": recent_posts,
                "summary": {
                    "total_categories": len(categories),
                    "total_tags": len(tags),
                    "total_authors": len(authors),
                    "category_names": [c["name"] for c in categories],
                    "tag_names": [t["name"] for t in tags],
                    "author_names": [a["name"] for a in authors],
                }
            }

            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps(context, indent=2)
                }]
            }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error fetching blog context: {str(e)}"
            }],
            "is_error": True
        }


async def get_sample_post(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get a sample published post to understand content structure.

    Args:
        category_slug (optional): Get a sample from a specific category

    Returns:
        A complete blog post with all fields, showing the exact content block structure.
    """
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # Build query
            query = f"{SUPABASE_URL}/rest/v1/blog_posts?select=*&status=eq.published&limit=1"

            if args.get("category_slug"):
                # First get category ID
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
                return {
                    "content": [{
                        "type": "text",
                        "text": "No published posts found. You'll need to create content following the documented block structure."
                    }]
                }

            post = posts[0]

            # Also get the tags for this post
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_post_tags?select=tag_id,blog_tags(slug,name)&post_id=eq.{post['id']}",
                headers=headers
            ) as resp:
                post_tags = await resp.json() if resp.status == 200 else []

            post["linked_tags"] = [
                {"slug": pt["blog_tags"]["slug"], "name": pt["blog_tags"]["name"]}
                for pt in post_tags if pt.get("blog_tags")
            ]

            return {
                "content": [{
                    "type": "text",
                    "text": f"Sample post structure:\n\n{json.dumps(post, indent=2)}"
                }]
            }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error fetching sample post: {str(e)}"
            }],
            "is_error": True
        }


async def check_slug_exists(args: dict[str, Any]) -> dict[str, Any]:
    """
    Check if a slug already exists for posts, categories, or tags.

    Args:
        slug: The slug to check
        table: Which table to check ('posts', 'categories', 'tags')

    Returns:
        Whether the slug exists and suggestions if it does.
    """
    try:
        slug = args.get("slug", "")
        table = args.get("table", "posts")

        table_map = {
            "posts": "blog_posts",
            "categories": "blog_categories",
            "tags": "blog_tags",
        }

        db_table = table_map.get(table, "blog_posts")

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            async with session.get(
                f"{SUPABASE_URL}/rest/v1/{db_table}?select=slug&slug=eq.{slug}",
                headers=headers
            ) as resp:
                results = await resp.json() if resp.status == 200 else []

            exists = len(results) > 0

            result = {
                "slug": slug,
                "table": table,
                "exists": exists,
            }

            if exists:
                result["suggestion"] = f"Slug '{slug}' already exists. Try: {slug}-2 or a more specific variation."

            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }]
            }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error checking slug: {str(e)}"
            }],
            "is_error": True
        }


# Tool definitions for Claude Agent SDK
QUERY_TOOLS = [
    {
        "name": "get_blog_context",
        "description": """Get complete blog context including all existing categories, tags, authors, and recent posts.

ALWAYS call this tool FIRST before generating any content. This helps you:
- Know which categories exist (use existing ones when appropriate)
- Know which tags exist (reuse instead of creating duplicates)
- Know which authors are available
- See recent posts to avoid duplicate topics

Returns: JSON with categories, tags, authors, and recent_posts arrays.""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "function": get_blog_context
    },
    {
        "name": "get_sample_post",
        "description": """Get a sample published post to understand the exact content block structure.

Call this if you need to see how existing posts are formatted, especially the content blocks.

Args:
    category_slug (optional): Get a sample from a specific category

Returns: A complete blog post JSON showing all fields and content block structure.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "category_slug": {
                    "type": "string",
                    "description": "Optional: Get sample from specific category"
                }
            },
            "required": []
        },
        "function": get_sample_post
    },
    {
        "name": "check_slug_exists",
        "description": """Check if a slug already exists before creating content.

Always check slugs before creating posts, categories, or tags to avoid conflicts.

Args:
    slug: The URL-friendly slug to check
    table: Which table - 'posts', 'categories', or 'tags'

Returns: Whether slug exists and suggestion if it does.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "The slug to check (lowercase, hyphens, no spaces)"
                },
                "table": {
                    "type": "string",
                    "enum": ["posts", "categories", "tags"],
                    "description": "Which table to check"
                }
            },
            "required": ["slug", "table"]
        },
        "function": check_slug_exists
    }
]
