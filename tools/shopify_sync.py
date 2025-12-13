"""
Shopify Sync - CLI handlers for syncing blog content to Shopify

This module provides functions for:
1. Syncing categories to Shopify Blogs
2. Syncing posts to Shopify Articles
3. Displaying sync status
4. Bulk sync operations
"""

from datetime import datetime
from typing import Optional
import aiohttp
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SUPABASE_URL, get_supabase_headers, SHOPIFY_DEFAULT_AUTHOR
from tools.shopify_tools import (
    sync_category_to_shopify,
    sync_post_to_shopify,
    get_shopify_visibility_label,
    clear_sync_cache,
)


# =============================================================================
# SUPABASE HELPERS
# =============================================================================

async def get_all_categories() -> list:
    """Fetch all categories from Supabase."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_categories?select=*&order=sort_order,name",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return []
    except Exception as e:
        print(f"Error fetching categories: {e}")
        return []


async def get_category_by_slug(slug: str) -> Optional[dict]:
    """Fetch a single category by slug."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_categories?slug=eq.{slug}&limit=1",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    categories = await resp.json()
                    return categories[0] if categories else None
                return None
    except Exception:
        return None


async def get_category_by_id(category_id: str) -> Optional[dict]:
    """Fetch a single category by ID."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_categories?id=eq.{category_id}&limit=1",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    categories = await resp.json()
                    return categories[0] if categories else None
                return None
    except Exception:
        return None


async def update_category_shopify_fields(category_id: str, shopify_blog_gid: str) -> bool:
    """Update category with Shopify sync info."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.patch(
                f"{SUPABASE_URL}/rest/v1/blog_categories?id=eq.{category_id}",
                headers=headers,
                json={
                    "shopify_blog_gid": shopify_blog_gid,
                    "shopify_synced_at": datetime.utcnow().isoformat(),
                }
            ) as resp:
                return resp.status in [200, 204]
    except Exception:
        return False


async def get_all_posts() -> list:
    """Fetch all posts from Supabase with related data."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?select=*,blog_categories(id,slug,name,shopify_blog_gid),blog_authors(id,slug,name)&order=updated_at.desc",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return []
    except Exception as e:
        print(f"Error fetching posts: {e}")
        return []


async def get_post_by_slug(slug: str) -> Optional[dict]:
    """Fetch a single post by slug with related data."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?slug=eq.{slug}&select=*,blog_categories(id,slug,name,shopify_blog_gid),blog_authors(id,slug,name)&limit=1",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    posts = await resp.json()
                    return posts[0] if posts else None
                return None
    except Exception:
        return None


async def get_post_by_id(post_id: str) -> Optional[dict]:
    """Fetch a single post by ID with related data."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?id=eq.{post_id}&select=*,blog_categories(id,slug,name,shopify_blog_gid),blog_authors(id,slug,name)&limit=1",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    posts = await resp.json()
                    return posts[0] if posts else None
                return None
    except Exception:
        return None


async def get_post_tags(post_id: str) -> list:
    """Fetch tags for a post."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_post_tags?post_id=eq.{post_id}&select=blog_tags(name)",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    results = await resp.json()
                    return [r['blog_tags']['name'] for r in results if r.get('blog_tags')]
                return []
    except Exception:
        return []


async def update_post_shopify_fields(
    post_id: str,
    shopify_article_id: Optional[str] = None,
    error: Optional[str] = None
) -> bool:
    """Update post with Shopify sync info."""
    try:
        update_data = {
            "shopify_synced_at": datetime.utcnow().isoformat(),
        }
        if shopify_article_id:
            update_data["shopify_article_id"] = shopify_article_id
            update_data["shopify_sync_error"] = None
        if error:
            update_data["shopify_sync_error"] = error

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


# =============================================================================
# CATEGORY SYNC FUNCTIONS
# =============================================================================

async def sync_all_categories(force: bool = False) -> dict:
    """
    Sync all categories to Shopify Blogs.

    Args:
        force: Force re-sync even if already synced (updates existing blogs)

    Returns:
        dict with keys: synced, failed, skipped
    """
    clear_sync_cache()  # Prevent duplicates across sync operations
    categories = await get_all_categories()

    if not categories:
        print("No categories found in database.")
        return {"synced": 0, "failed": 0, "skipped": 0}

    print(f"Found {len(categories)} categories to sync...")
    if force:
        print("Force mode: will re-sync all categories\n")
    else:
        print()

    synced = 0
    failed = 0
    skipped = 0

    for cat in categories:
        cat_id = cat['id']
        name = cat['name']
        slug = cat['slug']
        existing_gid = cat.get('shopify_blog_gid')
        seo = cat.get('seo')  # SEO data from Supabase

        # Skip if already synced and not forcing
        if existing_gid and not force:
            print(f"  [SKIP] {name} - already synced")
            skipped += 1
            continue

        # Print status
        if force and existing_gid:
            print(f"  Syncing: {name} (force)...", end=" ")
        else:
            print(f"  Syncing: {name}...", end=" ")

        result = await sync_category_to_shopify(
            category_id=cat_id,
            name=name,
            slug=slug,
            existing_blog_gid=existing_gid,  # Pass existing GID for update, fallback handles stale IDs
            seo=seo,
        )

        if result.get("success"):
            # Update Supabase with Shopify GID
            await update_category_shopify_fields(cat_id, result["shopify_blog_gid"])
            print(f"OK ({result.get('handle', slug)})")
            synced += 1
        else:
            print(f"FAILED: {result.get('error', 'Unknown error')}")
            failed += 1

    return {"synced": synced, "failed": failed, "skipped": skipped}


async def sync_category_by_slug(slug: str, force: bool = False) -> bool:
    """
    Sync a single category by slug.

    Args:
        slug: Category slug
        force: Force re-sync even if already synced

    Returns:
        True if successful
    """
    category = await get_category_by_slug(slug)

    if not category:
        print(f"Category not found: {slug}")
        return False

    existing_gid = category.get('shopify_blog_gid')

    if existing_gid and not force:
        print(f"Category '{category['name']}' already synced. Use --force to re-sync.")
        return True

    print(f"Syncing category: {category['name']}...")

    result = await sync_category_to_shopify(
        category_id=category['id'],
        name=category['name'],
        slug=slug,
        existing_blog_gid=existing_gid,  # Pass existing GID for update, fallback handles stale IDs
        seo=category.get('seo'),
    )

    if result.get("success"):
        await update_category_shopify_fields(category['id'], result["shopify_blog_gid"])
        print(f"Synced: {result.get('handle', slug)}")
        return True
    else:
        print(f"Failed: {result.get('error', 'Unknown error')}")
        return False


async def ensure_category_synced(category_id: str) -> Optional[str]:
    """
    Ensure a category is synced to Shopify, syncing if needed.

    Args:
        category_id: Supabase category UUID

    Returns:
        Shopify blog GID if successful, None otherwise
    """
    category = await get_category_by_id(category_id)

    if not category:
        return None

    existing_gid = category.get('shopify_blog_gid')

    if existing_gid:
        return existing_gid

    # Sync the category
    result = await sync_category_to_shopify(
        category_id=category_id,
        name=category['name'],
        slug=category['slug'],
        seo=category.get('seo'),
    )

    if result.get("success"):
        await update_category_shopify_fields(category_id, result["shopify_blog_gid"])
        return result["shopify_blog_gid"]

    return None


# =============================================================================
# POST SYNC FUNCTIONS
# =============================================================================

async def sync_post_by_slug(slug: str, force: bool = False) -> bool:
    """
    Sync a single post by slug.

    Args:
        slug: Post slug
        force: Force re-sync even if already synced

    Returns:
        True if successful or skipped, False if failed
    """
    post = await get_post_by_slug(slug)

    if not post:
        print(f"Post not found: {slug}")
        return False

    result = await _sync_single_post(post, force)
    return result in ("synced", "skipped")


async def sync_post_by_id(post_id: str, force: bool = False) -> bool:
    """
    Sync a single post by ID.

    Args:
        post_id: Post UUID
        force: Force re-sync even if already synced

    Returns:
        True if successful or skipped, False if failed
    """
    post = await get_post_by_id(post_id)

    if not post:
        print(f"Post not found: {post_id}")
        return False

    result = await _sync_single_post(post, force)
    return result in ("synced", "skipped")


async def _sync_single_post(post: dict, force: bool = False) -> str:
    """
    Internal function to sync a single post.

    Returns:
        "synced" if successfully synced
        "skipped" if post is up-to-date and not forced
        "failed" if sync failed
    """
    post_id = post['id']
    title = post['title']
    slug = post['slug']
    status = post.get('status', 'draft')
    existing_article_id = post.get('shopify_article_id')
    updated_at = post.get('updated_at', '')
    synced_at = post.get('shopify_synced_at', '')

    # Check if sync is needed
    needs_sync = (
        force or
        not existing_article_id or
        (updated_at and (not synced_at or updated_at > synced_at))
    )

    if not needs_sync:
        visibility = get_shopify_visibility_label(status)
        print(f"  [SKIP] {title[:50]} - up-to-date ({visibility})")
        return "skipped"

    # Ensure category is synced first
    category = post.get('blog_categories')
    if not category:
        print(f"  [FAIL] {title[:50]} - no category assigned")
        return "failed"

    shopify_blog_gid = category.get('shopify_blog_gid')
    if not shopify_blog_gid:
        print(f"  Syncing category '{category['name']}' first...")
        shopify_blog_gid = await ensure_category_synced(category['id'])
        if not shopify_blog_gid:
            print(f"  [FAIL] {title[:50]} - category sync failed")
            return "failed"

    # Get author name
    author = post.get('blog_authors', {})
    author_name = author.get('name') if author else SHOPIFY_DEFAULT_AUTHOR

    # Get tags
    tags = await get_post_tags(post_id)

    visibility = get_shopify_visibility_label(status)
    print(f"  Syncing: {title[:50]}... ({visibility})", end=" ")

    result = await sync_post_to_shopify(
        post_id=post_id,
        title=title,
        slug=slug,
        excerpt=post.get('excerpt', ''),
        content=post.get('content', []),
        status=status,
        shopify_blog_gid=shopify_blog_gid,
        author_name=author_name,
        featured_image=post.get('featured_image'),
        featured_image_alt=post.get('featured_image_alt'),
        seo=post.get('seo'),
        scheduled_at=post.get('scheduled_at'),
        tags=tags,
        existing_shopify_id=existing_article_id,
    )

    if result.get("success"):
        await update_post_shopify_fields(post_id, shopify_article_id=result["shopify_article_id"])
        print("OK")
        return "synced"
    else:
        error = result.get('error', 'Unknown error')
        await update_post_shopify_fields(post_id, error=error)
        print(f"FAILED: {error}")
        return "failed"


def _needs_sync(post: dict) -> bool:
    """Check if a post needs syncing."""
    shopify_article_id = post.get('shopify_article_id')
    updated_at = post.get('updated_at', '')
    synced_at = post.get('shopify_synced_at', '')

    # Never synced
    if not shopify_article_id:
        return True

    # Updated since last sync
    if updated_at and (not synced_at or updated_at > synced_at):
        return True

    return False


async def get_posts_needing_sync() -> list:
    """Get all posts that need syncing to Shopify."""
    posts = await get_all_posts()
    return [p for p in posts if _needs_sync(p)]


async def sync_all_posts(force: bool = False) -> dict:
    """
    Sync all posts to Shopify.

    Fetches ALL posts and syncs each one. Use force=True to re-sync
    posts that appear up-to-date.

    Args:
        force: Force re-sync even if post appears up-to-date

    Returns:
        dict with keys: synced, failed, skipped
    """
    clear_sync_cache()  # Prevent duplicates across sync operations
    posts = await get_all_posts()

    if not posts:
        print("No posts found in database.")
        return {"synced": 0, "failed": 0, "skipped": 0}

    print(f"Found {len(posts)} post(s) to sync...\n")

    synced = 0
    failed = 0
    skipped = 0

    for post in posts:
        result = await _sync_single_post(post, force=force)
        if result == "synced":
            synced += 1
        elif result == "skipped":
            skipped += 1
        else:
            failed += 1

    return {"synced": synced, "failed": failed, "skipped": skipped}


async def sync_pending_posts() -> dict:
    """
    Sync only posts that need syncing (smart sync).

    A post needs sync if:
    - shopify_article_id IS NULL (never synced), OR
    - updated_at > shopify_synced_at (updated since last sync)

    Returns:
        dict with keys: synced, failed, skipped
    """
    clear_sync_cache()  # Prevent duplicates across sync operations
    posts = await get_posts_needing_sync()

    if not posts:
        print("No posts need syncing. Use --force to re-sync all.")
        return {"synced": 0, "failed": 0, "skipped": 0}

    print(f"Found {len(posts)} post(s) needing sync...\n")

    synced = 0
    failed = 0

    for post in posts:
        result = await _sync_single_post(post, force=False)
        if result == "synced":
            synced += 1
        else:
            failed += 1

    return {"synced": synced, "failed": failed, "skipped": 0}


async def sync_recent(n: int, force: bool = False) -> dict:
    """
    Sync the N most recently updated posts.

    Args:
        n: Number of posts to sync
        force: Force re-sync even if already synced

    Returns:
        dict with keys: synced, failed, skipped
    """
    clear_sync_cache()  # Prevent duplicates across sync operations
    posts = await get_all_posts()
    posts = posts[:n]  # Already sorted by updated_at desc

    if not posts:
        print("No posts found.")
        return {"synced": 0, "failed": 0, "skipped": 0}

    print(f"Syncing {len(posts)} most recent post(s)...\n")

    synced = 0
    failed = 0
    skipped = 0

    for post in posts:
        result = await _sync_single_post(post, force=force)
        if result == "synced":
            synced += 1
        elif result == "skipped":
            skipped += 1
        else:
            failed += 1

    return {"synced": synced, "failed": failed, "skipped": skipped}


# =============================================================================
# STATUS DISPLAY FUNCTIONS
# =============================================================================

def _format_datetime(dt_str: str) -> str:
    """Format datetime string for display."""
    if not dt_str:
        return "—"
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return dt_str[:16] if len(dt_str) >= 16 else dt_str


def _get_sync_status(post: dict) -> tuple:
    """Get sync status emoji and label for a post."""
    shopify_article_id = post.get('shopify_article_id')
    shopify_sync_error = post.get('shopify_sync_error')
    updated_at = post.get('updated_at', '')
    synced_at = post.get('shopify_synced_at', '')

    if shopify_sync_error:
        return ("ERROR", shopify_sync_error[:30])

    if not shopify_article_id:
        return ("NOT SYNCED", "")

    if updated_at and synced_at and updated_at > synced_at:
        return ("STALE", "")

    return ("SYNCED", "")


async def show_sync_status() -> None:
    """Print table of post sync status."""
    posts = await get_all_posts()

    if not posts:
        print("No posts found.")
        return

    # Header
    print()
    print(f"{'TITLE':<42} {'STATUS':<10} {'SHOPIFY':<10} {'SYNC STATUS':<14} {'LAST EDIT':<18} {'LAST SYNC':<18}")
    print("-" * 112)

    for post in posts:
        title = post.get('title', '')[:40]
        status = post.get('status', 'draft')
        shopify_vis = get_shopify_visibility_label(status)
        sync_status, sync_note = _get_sync_status(post)
        updated_at = _format_datetime(post.get('updated_at', ''))
        synced_at = _format_datetime(post.get('shopify_synced_at', ''))

        # Color/emoji for sync status
        if sync_status == "SYNCED":
            sync_display = "SYNCED"
        elif sync_status == "STALE":
            sync_display = "STALE"
        elif sync_status == "ERROR":
            sync_display = "ERROR"
        else:
            sync_display = "NOT SYNCED"

        print(f"{title:<42} {status:<10} {shopify_vis:<10} {sync_display:<14} {updated_at:<18} {synced_at:<18}")

    print()

    # Summary counts
    synced_count = sum(1 for p in posts if p.get('shopify_article_id') and not _needs_sync(p))
    stale_count = sum(1 for p in posts if p.get('shopify_article_id') and _needs_sync(p))
    not_synced_count = sum(1 for p in posts if not p.get('shopify_article_id'))
    error_count = sum(1 for p in posts if p.get('shopify_sync_error'))

    print(f"Total: {len(posts)} | Synced: {synced_count} | Stale: {stale_count} | Not Synced: {not_synced_count} | Errors: {error_count}")


async def show_category_sync_status() -> None:
    """Print table of category sync status."""
    categories = await get_all_categories()

    if not categories:
        print("No categories found.")
        return

    # Header
    print()
    print(f"{'NAME':<30} {'SLUG':<25} {'SYNC STATUS':<15} {'LAST SYNC':<18}")
    print("-" * 90)

    for cat in categories:
        name = cat.get('name', '')[:28]
        slug = cat.get('slug', '')[:23]
        shopify_gid = cat.get('shopify_blog_gid')
        synced_at = _format_datetime(cat.get('shopify_synced_at', ''))

        if shopify_gid:
            sync_status = "SYNCED"
        else:
            sync_status = "NOT SYNCED"
            synced_at = "—"

        print(f"{name:<30} {slug:<25} {sync_status:<15} {synced_at:<18}")

    print()

    # Summary
    synced_count = sum(1 for c in categories if c.get('shopify_blog_gid'))
    not_synced_count = len(categories) - synced_count

    print(f"Total: {len(categories)} | Synced: {synced_count} | Not Synced: {not_synced_count}")
