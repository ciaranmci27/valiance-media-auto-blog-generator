"""
Blog Generator Tools

These tools allow Claude to interact with the Supabase database
to create and manage blog content autonomously.
"""

from .query_tools import (
    get_blog_context,
    get_sample_post,
    check_slug_exists,
    get_posts_without_images,
    QUERY_TOOLS,
)

from .write_tools import (
    create_blog_post,
    create_category,
    create_tag,
    link_tags_to_post,
    update_post_status,
    update_post_image,
    WRITE_TOOLS,
)

from .idea_tools import (
    get_and_claim_blog_idea,
    complete_blog_idea,
    fail_blog_idea,
    skip_blog_idea,
    get_idea_queue_status,
    IDEA_TOOLS,
)

__all__ = [
    # Query tools
    "get_blog_context",
    "get_sample_post",
    "check_slug_exists",
    "get_posts_without_images",
    "QUERY_TOOLS",
    # Write tools
    "create_blog_post",
    "create_category",
    "create_tag",
    "link_tags_to_post",
    "update_post_status",
    "update_post_image",
    "WRITE_TOOLS",
    # Idea tools
    "get_and_claim_blog_idea",
    "complete_blog_idea",
    "fail_blog_idea",
    "skip_blog_idea",
    "get_idea_queue_status",
    "IDEA_TOOLS",
]
