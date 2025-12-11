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
    """
    Create a new blog post in Supabase.

    Args:
        slug: URL-friendly identifier (lowercase, hyphens)
        title: Post title
        excerpt: Short description (2-3 sentences)
        content: Array of content blocks (JSONB)
        author_id: UUID of the author
        category_id: UUID of the category (optional)
        featured_image: URL to featured image (optional)
        featured_image_alt: Alt text for featured image (optional)
        reading_time: Estimated minutes to read (optional, auto-calculated if not provided)
        featured: Whether to feature this post (default: false)
        seo: SEO metadata object (optional)
        status: 'draft', 'published', or 'archived' (default: from config)

    Returns:
        The created post with its ID
    """
    try:
        # Build the post data
        post_data = {
            "slug": args["slug"],
            "title": args["title"],
            "excerpt": args["excerpt"],
            "content": args["content"],  # Should be array of content blocks
            "author_id": args["author_id"],
            "status": args.get("status", DEFAULT_STATUS),
            "featured": args.get("featured", False),
            "exclude_from_search": args.get("exclude_from_search", False),
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
            # Auto-calculate reading time (~200 words per minute)
            content_text = json.dumps(args["content"])
            word_count = len(content_text.split())
            post_data["reading_time"] = max(1, word_count // 200)

        if args.get("seo"):
            post_data["seo"] = args["seo"]

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            async with session.post(
                f"{SUPABASE_URL}/rest/v1/blog_posts",
                headers=headers,
                json=post_data
            ) as resp:
                if resp.status in [200, 201]:
                    result = await resp.json()
                    created_post = result[0] if isinstance(result, list) else result

                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Successfully created blog post!\n\nPost ID: {created_post['id']}\nSlug: {created_post['slug']}\nTitle: {created_post['title']}\nStatus: {created_post['status']}\n\nIMPORTANT: If you need to add tags, use the link_tags_to_post tool with this post_id: {created_post['id']}"
                        }]
                    }
                else:
                    error = await resp.text()
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Failed to create post (HTTP {resp.status}): {error}"
                        }],
                        "is_error": True
                    }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error creating blog post: {str(e)}"
            }],
            "is_error": True
        }


async def create_category(args: dict[str, Any]) -> dict[str, Any]:
    """
    Create a new blog category.

    Only create a new category if absolutely necessary - prefer using existing categories.

    Args:
        slug: URL-friendly identifier
        name: Display name
        description: Category description (optional)
        seo: SEO metadata object (optional)

    Returns:
        The created category with its ID
    """
    try:
        category_data = {
            "slug": args["slug"],
            "name": args["name"],
        }

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

                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Successfully created category!\n\nCategory ID: {created['id']}\nSlug: {created['slug']}\nName: {created['name']}\n\nUse this category_id when creating posts: {created['id']}"
                        }]
                    }
                else:
                    error = await resp.text()
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Failed to create category (HTTP {resp.status}): {error}"
                        }],
                        "is_error": True
                    }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error creating category: {str(e)}"
            }],
            "is_error": True
        }


async def create_tag(args: dict[str, Any]) -> dict[str, Any]:
    """
    Create a new blog tag.

    Only create a new tag if it doesn't already exist - check existing tags first.

    Args:
        slug: URL-friendly identifier (lowercase, hyphens)
        name: Display name

    Returns:
        The created tag with its ID
    """
    try:
        tag_data = {
            "slug": args["slug"],
            "name": args["name"],
        }

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

                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Successfully created tag!\n\nTag ID: {created['id']}\nSlug: {created['slug']}\nName: {created['name']}\n\nUse this tag_id when linking to posts: {created['id']}"
                        }]
                    }
                else:
                    error = await resp.text()
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Failed to create tag (HTTP {resp.status}): {error}"
                        }],
                        "is_error": True
                    }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error creating tag: {str(e)}"
            }],
            "is_error": True
        }


async def link_tags_to_post(args: dict[str, Any]) -> dict[str, Any]:
    """
    Link tags to a blog post via the junction table.

    Call this AFTER creating the post to associate tags with it.

    Args:
        post_id: UUID of the blog post
        tag_ids: Array of tag UUIDs to link

    Returns:
        Confirmation of linked tags
    """
    try:
        post_id = args["post_id"]
        tag_ids = args["tag_ids"]

        if not tag_ids:
            return {
                "content": [{
                    "type": "text",
                    "text": "No tags provided to link."
                }]
            }

        # Build insert data for junction table
        links = [{"post_id": post_id, "tag_id": tag_id} for tag_id in tag_ids]

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            async with session.post(
                f"{SUPABASE_URL}/rest/v1/blog_post_tags",
                headers=headers,
                json=links
            ) as resp:
                if resp.status in [200, 201]:
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Successfully linked {len(tag_ids)} tag(s) to post {post_id}"
                        }]
                    }
                else:
                    error = await resp.text()
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Failed to link tags (HTTP {resp.status}): {error}"
                        }],
                        "is_error": True
                    }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error linking tags: {str(e)}"
            }],
            "is_error": True
        }


async def update_post_status(args: dict[str, Any]) -> dict[str, Any]:
    """
    Update the status of a blog post.

    Args:
        post_id: UUID of the post
        status: New status ('draft', 'published', 'archived')

    Returns:
        Confirmation of the update
    """
    try:
        post_id = args["post_id"]
        status = args["status"]

        if status not in ["draft", "published", "archived"]:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Invalid status '{status}'. Must be 'draft', 'published', or 'archived'."
                }],
                "is_error": True
            }

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            async with session.patch(
                f"{SUPABASE_URL}/rest/v1/blog_posts?id=eq.{post_id}",
                headers=headers,
                json={"status": status, "updated_at": "now()"}
            ) as resp:
                if resp.status in [200, 204]:
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Successfully updated post {post_id} status to '{status}'"
                        }]
                    }
                else:
                    error = await resp.text()
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Failed to update status (HTTP {resp.status}): {error}"
                        }],
                        "is_error": True
                    }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error updating status: {str(e)}"
            }],
            "is_error": True
        }


# Tool definitions for Claude Agent SDK
WRITE_TOOLS = [
    {
        "name": "create_blog_post",
        "description": """Create a new blog post in Supabase.

IMPORTANT: Before calling this tool:
1. Call get_blog_context to know existing categories, tags, and authors
2. Check the slug doesn't exist with check_slug_exists
3. Get author_id from the context (use existing author)
4. Get category_id from context (use existing category when appropriate)

Content must be an array of content blocks with this structure:
[
  {"id": "unique-id", "type": "paragraph", "data": {"text": "..."}},
  {"id": "unique-id", "type": "heading", "data": {"level": 2, "text": "..."}},
  ...
]

Supported block types: paragraph, heading, quote, list, checklist, proscons, image,
gallery, video, embed, table, stats, accordion, button, tableOfContents, code, callout, divider

After creating the post, use link_tags_to_post to add tags.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "URL-friendly slug (lowercase, hyphens, no spaces). Example: 'how-to-fix-your-slice'"
                },
                "title": {
                    "type": "string",
                    "description": "Post title. Example: 'How to Fix Your Slice: A Complete Guide'"
                },
                "excerpt": {
                    "type": "string",
                    "description": "Short description (2-3 sentences) for previews and SEO"
                },
                "content": {
                    "type": "array",
                    "description": "Array of content blocks. Each block has id, type, and data properties.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "type": {"type": "string"},
                            "data": {"type": "object"}
                        },
                        "required": ["id", "type", "data"]
                    }
                },
                "author_id": {
                    "type": "string",
                    "description": "UUID of the author (get from get_blog_context)"
                },
                "category_id": {
                    "type": "string",
                    "description": "UUID of the category (optional, get from get_blog_context)"
                },
                "featured_image": {
                    "type": "string",
                    "description": "URL to featured image (optional)"
                },
                "featured_image_alt": {
                    "type": "string",
                    "description": "Alt text for featured image (required if featured_image provided)"
                },
                "reading_time": {
                    "type": "integer",
                    "description": "Estimated minutes to read (auto-calculated if not provided)"
                },
                "featured": {
                    "type": "boolean",
                    "description": "Whether to feature this post on homepage (default: false)"
                },
                "seo": {
                    "type": "object",
                    "description": "SEO metadata: {title, description, keywords[], image}",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "keywords": {"type": "array", "items": {"type": "string"}},
                        "image": {"type": "string"}
                    }
                },
                "status": {
                    "type": "string",
                    "enum": ["draft", "published", "archived"],
                    "description": "Post status (default: 'draft' for review before publishing)"
                }
            },
            "required": ["slug", "title", "excerpt", "content", "author_id"]
        },
        "function": create_blog_post
    },
    {
        "name": "create_category",
        "description": """Create a new blog category.

IMPORTANT: Only create a new category if absolutely necessary!
First check get_blog_context to see existing categories. Most posts should use existing categories.

Common categories for golf blogs: Instruction, Equipment, Course Reviews, Tips & Tricks, Mental Game, etc.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "URL-friendly slug (lowercase, hyphens)"
                },
                "name": {
                    "type": "string",
                    "description": "Display name for the category"
                },
                "description": {
                    "type": "string",
                    "description": "Short description of what posts belong in this category"
                },
                "seo": {
                    "type": "object",
                    "description": "SEO metadata for category page",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "keywords": {"type": "array", "items": {"type": "string"}}
                    }
                }
            },
            "required": ["slug", "name"]
        },
        "function": create_category
    },
    {
        "name": "create_tag",
        "description": """Create a new blog tag.

IMPORTANT: Check existing tags from get_blog_context first to avoid duplicates!
Tags are for specific topics within a post. Reuse existing tags when possible.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "URL-friendly slug (lowercase, hyphens). Example: 'swing-mechanics'"
                },
                "name": {
                    "type": "string",
                    "description": "Display name. Example: 'Swing Mechanics'"
                }
            },
            "required": ["slug", "name"]
        },
        "function": create_tag
    },
    {
        "name": "link_tags_to_post",
        "description": """Link tags to a blog post.

Call this AFTER creating the post. Gets the post_id from create_blog_post result.
Gets tag_ids from get_blog_context or create_tag results.

A post should typically have 3-7 relevant tags.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {
                    "type": "string",
                    "description": "UUID of the blog post (from create_blog_post result)"
                },
                "tag_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Array of tag UUIDs to link to the post"
                }
            },
            "required": ["post_id", "tag_ids"]
        },
        "function": link_tags_to_post
    },
    {
        "name": "update_post_status",
        "description": """Update the status of a blog post.

Use this to publish a draft or archive old content.

Statuses:
- draft: Not visible on site, for review
- published: Live and visible
- archived: Hidden but preserved""",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {
                    "type": "string",
                    "description": "UUID of the post to update"
                },
                "status": {
                    "type": "string",
                    "enum": ["draft", "published", "archived"],
                    "description": "New status for the post"
                }
            },
            "required": ["post_id", "status"]
        },
        "function": update_post_status
    }
]
