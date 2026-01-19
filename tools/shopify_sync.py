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
    fetch_all_shopify_blogs,
    fetch_all_shopify_articles,
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

        # Debug: Show SEO data being synced
        if seo and isinstance(seo, dict) and any(seo.values()):
            print(f"  [DEBUG] SEO data for {name}: {seo}")
        elif seo:
            print(f"  [DEBUG] SEO data type: {type(seo)}, value: {seo}")

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


# =============================================================================
# IMPORT FUNCTIONS (CMS -> Supabase)
# =============================================================================

async def _get_category_by_slug_supabase(slug: str) -> Optional[dict]:
    """Check if a category exists in Supabase by slug."""
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


async def _insert_category_supabase(category_data: dict) -> tuple[bool, str]:
    """Insert a new category into Supabase.

    Returns:
        Tuple of (success, error_message)
    """
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.post(
                f"{SUPABASE_URL}/rest/v1/blog_categories",
                headers=headers,
                json=category_data
            ) as resp:
                if resp.status in [200, 201]:
                    return True, ""
                else:
                    error_text = await resp.text()
                    return False, f"HTTP {resp.status}: {error_text[:200]}"
    except Exception as e:
        return False, str(e)


async def _update_category_supabase(category_id: str, category_data: dict) -> bool:
    """Update an existing category in Supabase."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.patch(
                f"{SUPABASE_URL}/rest/v1/blog_categories?id=eq.{category_id}",
                headers=headers,
                json=category_data
            ) as resp:
                return resp.status in [200, 204]
    except Exception:
        return False


async def import_categories_from_shopify(force_pull: bool = False) -> dict:
    """
    Import categories (blogs) from Shopify into Supabase.

    This is a reverse sync - pulling existing blogs from Shopify
    into Supabase as categories. Useful when setting up the generator
    with an existing Shopify store.

    Args:
        force_pull: If True, overwrite existing Supabase categories with Shopify data.
                   If False (default), skip categories that already exist.

    Returns:
        dict with keys: imported, updated, skipped, errors
    """
    print("Fetching blogs from Shopify...")

    shopify_blogs = await fetch_all_shopify_blogs()

    if not shopify_blogs:
        print("No blogs found in Shopify (or fetch failed).")
        return {"imported": 0, "updated": 0, "skipped": 0, "errors": []}

    print(f"Found {len(shopify_blogs)} blogs in Shopify\n")

    imported = 0
    updated = 0
    skipped = 0
    errors = []

    for blog in shopify_blogs:
        gid = blog.get("id", "")
        handle = blog.get("handle", "")
        title = blog.get("title", "")

        if not handle:
            errors.append(f"Blog {gid} has no handle, skipping")
            continue

        # Use handle as slug (they're equivalent in Shopify)
        slug = handle

        # Check if category already exists in Supabase
        existing = await _get_category_by_slug_supabase(slug)

        if existing:
            if force_pull:
                # Update existing category with Shopify data
                update_data = {
                    "name": title,
                    "shopify_blog_gid": gid,
                    "shopify_synced_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                }
                # Note: Shopify blogs don't have descriptions

                success = await _update_category_supabase(existing["id"], update_data)
                if success:
                    print(f"  [UPDATE] {title} ({slug})")
                    updated += 1
                else:
                    errors.append(f"Failed to update {slug}")
            else:
                print(f"  [SKIP] {title} ({slug}) - already exists")
                skipped += 1
        else:
            # Insert new category
            insert_data = {
                "slug": slug,
                "name": title,
                "description": None,  # Shopify blogs don't have descriptions
                "shopify_blog_gid": gid,
                "shopify_synced_at": datetime.utcnow().isoformat(),
            }

            success, error_msg = await _insert_category_supabase(insert_data)
            if success:
                print(f"  [IMPORT] {title} ({slug})")
                imported += 1
            else:
                print(f"  [FAIL] {title} ({slug}) - {error_msg}")
                errors.append(f"Failed to import {slug}: {error_msg}")

    # Summary
    print()
    print(f"Import complete: {imported} imported, {updated} updated, {skipped} skipped")
    if errors:
        print(f"Errors: {len(errors)}")
        for err in errors[:5]:  # Show first 5 errors
            print(f"  - {err}")

    return {
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }


# =============================================================================
# TAG IMPORT (Shopify → Supabase)
# =============================================================================

def _slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    import re
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    slug = re.sub(r'^-+|-+$', '', slug)
    return slug


async def _get_tag_by_slug_supabase(slug: str) -> Optional[dict]:
    """Check if a tag exists in Supabase by slug."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_tags?slug=eq.{slug}&limit=1",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    tags = await resp.json()
                    return tags[0] if tags else None
                return None
    except Exception:
        return None


async def _insert_tag_supabase(tag_data: dict) -> tuple[bool, str]:
    """Insert a new tag into Supabase. Returns (success, error_message)."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.post(
                f"{SUPABASE_URL}/rest/v1/blog_tags",
                headers=headers,
                json=tag_data
            ) as resp:
                if resp.status in [200, 201]:
                    return True, ""
                else:
                    error_text = await resp.text()
                    return False, f"HTTP {resp.status}: {error_text[:200]}"
    except Exception as e:
        return False, str(e)


async def _update_tag_supabase(tag_id: str, update_data: dict) -> bool:
    """Update an existing tag in Supabase."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.patch(
                f"{SUPABASE_URL}/rest/v1/blog_tags?id=eq.{tag_id}",
                headers=headers,
                json=update_data
            ) as resp:
                return resp.status in [200, 204]
    except Exception:
        return False


async def import_tags_from_shopify(force_pull: bool = False) -> dict:
    """
    Import tags from Shopify into Supabase.

    Shopify doesn't have a dedicated tags API - tags are strings attached to articles.
    This function fetches all articles and extracts unique tags.

    Args:
        force_pull: If True, overwrite existing Supabase tags with Shopify data.
                   If False (default), skip tags that already exist.

    Returns:
        dict with keys: imported, updated, skipped, errors
    """
    print("Fetching articles from Shopify to extract tags...")

    articles = await fetch_all_shopify_articles()

    if not articles:
        print("No articles found in Shopify (or fetch failed).")
        return {"imported": 0, "updated": 0, "skipped": 0, "errors": []}

    # Extract unique tags from all articles
    unique_tags = set()
    for article in articles:
        tags = article.get("tags", [])
        for tag in tags:
            if tag and tag.strip():
                unique_tags.add(tag.strip())

    if not unique_tags:
        print("No tags found in Shopify articles.")
        return {"imported": 0, "updated": 0, "skipped": 0, "errors": []}

    print(f"Found {len(unique_tags)} unique tags across {len(articles)} articles\n")

    imported = 0
    updated = 0
    skipped = 0
    errors = []

    for tag_name in sorted(unique_tags):
        slug = _slugify(tag_name)

        if not slug:
            errors.append(f"Tag '{tag_name}' produces empty slug, skipping")
            continue

        # Check if tag already exists in Supabase
        existing = await _get_tag_by_slug_supabase(slug)

        if existing:
            if force_pull:
                # Update existing tag
                update_data = {
                    "name": tag_name,
                }

                success = await _update_tag_supabase(existing["id"], update_data)
                if success:
                    print(f"  [UPDATE] {tag_name} ({slug})")
                    updated += 1
                else:
                    errors.append(f"Failed to update {slug}")
            else:
                print(f"  [SKIP] {tag_name} ({slug}) - already exists")
                skipped += 1
        else:
            # Insert new tag
            insert_data = {
                "slug": slug,
                "name": tag_name,
            }

            success, error_msg = await _insert_tag_supabase(insert_data)
            if success:
                print(f"  [IMPORT] {tag_name} ({slug})")
                imported += 1
            else:
                print(f"  [FAIL] {tag_name} ({slug}) - {error_msg}")
                errors.append(f"Failed to import {slug}: {error_msg}")

    # Summary
    print()
    print(f"Import complete: {imported} imported, {updated} updated, {skipped} skipped")
    if errors:
        print(f"Errors: {len(errors)}")
        for err in errors[:5]:
            print(f"  - {err}")

    return {
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }


# =============================================================================
# POST IMPORT (Shopify → Supabase)
# =============================================================================

async def _get_post_by_slug_supabase(slug: str) -> Optional[dict]:
    """Check if a post exists in Supabase by slug."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?slug=eq.{slug}&limit=1",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    posts = await resp.json()
                    return posts[0] if posts else None
                return None
    except Exception:
        return None


async def _get_category_by_shopify_gid(gid: str) -> Optional[dict]:
    """Get Supabase category by Shopify GID."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_categories?shopify_blog_gid=eq.{gid}&limit=1",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    categories = await resp.json()
                    return categories[0] if categories else None
                return None
    except Exception:
        return None


async def _get_tag_by_name_supabase(name: str) -> Optional[dict]:
    """Get Supabase tag by name (case-insensitive via slug)."""
    slug = _slugify(name)
    return await _get_tag_by_slug_supabase(slug)


async def _get_default_author_id() -> Optional[str]:
    """Get the default author ID from Supabase."""
    from config import DEFAULT_AUTHOR_SLUG
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_authors?slug=eq.{DEFAULT_AUTHOR_SLUG}&limit=1",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    authors = await resp.json()
                    return authors[0]["id"] if authors else None
                return None
    except Exception:
        return None


async def _insert_post_supabase(post_data: dict) -> tuple[bool, str, Optional[str]]:
    """Insert a new post into Supabase. Returns (success, error_message, post_id)."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            headers["Prefer"] = "return=representation"
            async with session.post(
                f"{SUPABASE_URL}/rest/v1/blog_posts",
                headers=headers,
                json=post_data
            ) as resp:
                if resp.status in [200, 201]:
                    result = await resp.json()
                    post_id = result[0]["id"] if result else None
                    return True, "", post_id
                else:
                    error_text = await resp.text()
                    return False, f"HTTP {resp.status}: {error_text[:200]}", None
    except Exception as e:
        return False, str(e), None


async def _update_post_supabase(post_id: str, update_data: dict) -> bool:
    """Update an existing post in Supabase."""
    try:
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


async def _create_post_tag_relations(post_id: str, tag_ids: list) -> int:
    """Create post-tag relationships. Returns number of relations created."""
    if not tag_ids:
        return 0

    created = 0
    for tag_id in tag_ids:
        try:
            async with aiohttp.ClientSession() as session:
                headers = get_supabase_headers()
                async with session.post(
                    f"{SUPABASE_URL}/rest/v1/blog_post_tags",
                    headers=headers,
                    json={"post_id": post_id, "tag_id": tag_id}
                ) as resp:
                    if resp.status in [200, 201]:
                        created += 1
        except Exception:
            pass
    return created


async def _delete_post_tag_relations(post_id: str) -> bool:
    """Delete all post-tag relationships for a post."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()
            async with session.delete(
                f"{SUPABASE_URL}/rest/v1/blog_post_tags?post_id=eq.{post_id}",
                headers=headers
            ) as resp:
                return resp.status in [200, 204]
    except Exception:
        return False


async def import_posts_from_shopify(force_pull: bool = False) -> dict:
    """
    Import posts (articles) from Shopify into Supabase.

    This is a reverse sync - pulling existing articles from Shopify
    into Supabase. Useful when setting up the generator with an existing store.

    Shopify HTML content is stored as a single HTML content block in the
    content JSONB field, preserving the original formatting.

    Prerequisites:
    - Import categories first with --shopify-import-categories
    - Import tags first with --shopify-import-tags

    Args:
        force_pull: If True, overwrite existing Supabase posts with Shopify data.
                   If False (default), skip posts that already exist.

    Returns:
        dict with keys: imported, updated, skipped, errors
    """
    print("Fetching articles from Shopify...")

    articles = await fetch_all_shopify_articles()

    if not articles:
        print("No articles found in Shopify (or fetch failed).")
        return {"imported": 0, "updated": 0, "skipped": 0, "errors": []}

    print(f"Found {len(articles)} articles in Shopify\n")

    # Get default author
    default_author_id = await _get_default_author_id()
    if not default_author_id:
        print("Warning: No default author found. Posts will be created without author.")

    imported = 0
    updated = 0
    skipped = 0
    errors = []

    for article in articles:
        gid = article.get("id", "")
        handle = article.get("handle", "")
        title = article.get("title", "")
        content_html = article.get("body", "")  # 'body' is the field name in Admin API
        excerpt = article.get("summary", "") or ""  # 'summary' is the field name in Admin API
        published_at = article.get("publishedAt", "")
        tags = article.get("tags", [])

        if not handle:
            errors.append(f"Article {gid} has no handle, skipping")
            continue

        slug = handle

        # Clean up excerpt
        # Truncate long excerpts, but don't set placeholder text
        # Empty excerpts should stay empty to avoid overwriting Shopify data
        if excerpt and len(excerpt) > 300:
            excerpt = excerpt[:297] + "..."

        # Store HTML content as a single HTML block
        content_blocks = [{"type": "html", "content": content_html}] if content_html else []

        # SAFETY CHECK: Validate content is not empty before proceeding
        content_length = len(content_html.strip()) if content_html else 0
        if content_length < 50:
            print(f"  [SKIP] {title[:50]}... ({slug}) - empty/minimal content ({content_length} chars)")
            errors.append(f"Skipped {slug}: empty content from Shopify ({content_length} chars)")
            skipped += 1
            continue

        # Get featured image
        image_data = article.get("image", {})
        featured_image = image_data.get("url") if image_data else None
        featured_image_alt = image_data.get("altText") if image_data else None

        # Resolve category (blog)
        blog_data = article.get("blog", {})
        blog_gid = blog_data.get("id") if blog_data else None
        category_id = None
        if blog_gid:
            cat = await _get_category_by_shopify_gid(blog_gid)
            if cat:
                category_id = cat["id"]

        # Resolve tags
        supabase_tag_ids = []
        for tag_name in tags:
            tag = await _get_tag_by_name_supabase(tag_name)
            if tag:
                supabase_tag_ids.append(tag["id"])

        # Get SEO data
        seo_data = article.get("seo", {})
        seo = {}
        if seo_data:
            if seo_data.get("title"):
                seo["title"] = seo_data["title"]
            if seo_data.get("description"):
                seo["description"] = seo_data["description"]

        # Check if post already exists in Supabase
        existing = await _get_post_by_slug_supabase(slug)

        if existing:
            if force_pull:
                # Update existing post with Shopify data
                update_data = {
                    "title": title,
                    "excerpt": excerpt,
                    "content": content_blocks,
                    "status": "published" if published_at else "draft",
                    "featured_image": featured_image,
                    "featured_image_alt": featured_image_alt,
                    "category_id": category_id,
                    "shopify_article_id": gid,
                    "shopify_synced_at": datetime.utcnow().isoformat(),
                    "shopify_sync_error": None,
                }
                if seo:
                    update_data["seo"] = seo

                success = await _update_post_supabase(existing["id"], update_data)
                if success:
                    # Update tag relations - SAFETY: only modify tags if we have tags to set
                    # This prevents accidental tag deletion when import fails to resolve tags
                    if supabase_tag_ids:
                        await _delete_post_tag_relations(existing["id"])
                        await _create_post_tag_relations(existing["id"], supabase_tag_ids)
                        tag_info = f" [{len(supabase_tag_ids)} tags]"
                    else:
                        # Don't delete existing tags if we have no new tags
                        # This is safer - preserves existing data
                        tag_info = " [tags preserved]"
                    print(f"  [UPDATE] {title[:50]}... ({slug}){tag_info}")
                    updated += 1
                else:
                    errors.append(f"Failed to update {slug}")
            else:
                print(f"  [SKIP] {title[:50]}... ({slug}) - already exists")
                skipped += 1
        else:
            # Insert new post
            insert_data = {
                "slug": slug,
                "title": title,
                "excerpt": excerpt,
                "content": content_blocks,
                "status": "published" if published_at else "draft",
                "featured_image": featured_image,
                "featured_image_alt": featured_image_alt,
                "author_id": default_author_id,
                "category_id": category_id,
                "shopify_article_id": gid,
                "shopify_synced_at": datetime.utcnow().isoformat(),
            }
            if seo:
                insert_data["seo"] = seo

            # Parse date if available
            if published_at:
                try:
                    insert_data["created_at"] = published_at
                except Exception:
                    pass

            success, error_msg, new_post_id = await _insert_post_supabase(insert_data)
            if success and new_post_id:
                # Create tag relations
                await _create_post_tag_relations(new_post_id, supabase_tag_ids)
                tag_count = len(supabase_tag_ids)
                tag_info = f" [{tag_count} tags]" if tag_count else ""
                print(f"  [IMPORT] {title[:50]}... ({slug}){tag_info}")
                imported += 1
            else:
                print(f"  [FAIL] {title[:50]}... ({slug}) - {error_msg}")
                errors.append(f"Failed to import {slug}: {error_msg}")

    # Summary
    print()
    print(f"Import complete: {imported} imported, {updated} updated, {skipped} skipped")
    if errors:
        print(f"Errors: {len(errors)}")
        for err in errors[:5]:
            print(f"  - {err}")

    return {
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }


async def import_single_post_from_shopify(slug: str) -> bool:
    """
    Import a single post from Shopify into Supabase by slug/handle.

    This always overwrites existing data - it's meant for pulling fresh
    content from Shopify to fix issues or restore content.

    Prerequisites:
    - Import categories first with --shopify-import-categories
    - Import tags first with --shopify-import-tags (optional but recommended)

    Args:
        slug: The article handle (slug) to import

    Returns:
        True if successful, False otherwise
    """
    print(f"Fetching article '{slug}' from Shopify...")

    # Fetch all articles and find the one we want
    articles = await fetch_all_shopify_articles()

    if not articles:
        print("Error: Could not fetch articles from Shopify.")
        return False

    # Find the article by handle
    article = None
    for a in articles:
        if a.get("handle") == slug:
            article = a
            break

    if not article:
        print(f"Error: Article with slug '{slug}' not found in Shopify.")
        available = [a.get("handle", "?") for a in articles[:10]]
        print(f"Available slugs: {', '.join(available)}")
        if len(articles) > 10:
            print(f"  ... and {len(articles) - 10} more")
        return False

    # Extract article data
    gid = article.get("id", "")
    handle = article.get("handle", "")
    title = article.get("title", "")
    content_html = article.get("body", "")
    excerpt = article.get("summary", "") or ""
    published_at = article.get("publishedAt", "")
    tags = article.get("tags", [])

    # Clean up excerpt (truncate if too long, but don't add placeholder)
    if excerpt and len(excerpt) > 300:
        excerpt = excerpt[:297] + "..."

    # Store HTML content as a single HTML block
    content_blocks = [{"type": "html", "content": content_html}] if content_html else []

    # SAFETY CHECK: Validate content
    content_length = len(content_html.strip()) if content_html else 0
    if content_length < 50:
        print(f"Error: Shopify article has empty/minimal content ({content_length} chars)")
        print("This may indicate the article doesn't exist or has no body content.")
        return False

    print(f"Found article: {title}")
    print(f"  Content: {content_length} chars")

    # Get featured image
    image_data = article.get("image", {})
    featured_image = image_data.get("url") if image_data else None
    featured_image_alt = image_data.get("altText") if image_data else None

    # Resolve category (blog)
    blog_data = article.get("blog", {})
    blog_gid = blog_data.get("id") if blog_data else None
    category_id = None
    if blog_gid:
        cat = await _get_category_by_shopify_gid(blog_gid)
        if cat:
            category_id = cat["id"]
            print(f"  Category: {cat.get('name', '?')}")
        else:
            print(f"  Warning: Blog {blog_gid} not found in Supabase. Run --shopify-import-categories first.")

    # Resolve tags
    supabase_tag_ids = []
    for tag_name in tags:
        tag = await _get_tag_by_name_supabase(tag_name)
        if tag:
            supabase_tag_ids.append(tag["id"])
    print(f"  Tags: {len(tags)} in Shopify, {len(supabase_tag_ids)} matched in Supabase")

    # Get default author
    default_author_id = await _get_default_author_id()

    # Check if post already exists in Supabase
    existing = await _get_post_by_slug_supabase(slug)

    if existing:
        print(f"  Updating existing Supabase post...")

        update_data = {
            "title": title,
            "excerpt": excerpt,
            "content": content_blocks,
            "status": "published" if published_at else "draft",
            "featured_image": featured_image,
            "featured_image_alt": featured_image_alt,
            "category_id": category_id,
            "shopify_article_id": gid,
            "shopify_synced_at": datetime.utcnow().isoformat(),
            "shopify_sync_error": None,
        }

        success = await _update_post_supabase(existing["id"], update_data)
        if success:
            # Update tag relations if we have tags
            if supabase_tag_ids:
                await _delete_post_tag_relations(existing["id"])
                await _create_post_tag_relations(existing["id"], supabase_tag_ids)
                tag_info = f" with {len(supabase_tag_ids)} tags"
            else:
                tag_info = " (tags preserved)"
            print(f"  [SUCCESS] Updated '{title}'{tag_info}")
            return True
        else:
            print(f"  [FAILED] Could not update post in Supabase")
            return False
    else:
        print(f"  Creating new Supabase post...")

        insert_data = {
            "slug": slug,
            "title": title,
            "excerpt": excerpt,
            "content": content_blocks,
            "status": "published" if published_at else "draft",
            "featured_image": featured_image,
            "featured_image_alt": featured_image_alt,
            "author_id": default_author_id,
            "category_id": category_id,
            "shopify_article_id": gid,
            "shopify_synced_at": datetime.utcnow().isoformat(),
        }

        if published_at:
            try:
                insert_data["created_at"] = published_at
            except Exception:
                pass

        success, error_msg, new_post_id = await _insert_post_supabase(insert_data)
        if success and new_post_id:
            await _create_post_tag_relations(new_post_id, supabase_tag_ids)
            tag_info = f" with {len(supabase_tag_ids)} tags" if supabase_tag_ids else ""
            print(f"  [SUCCESS] Imported '{title}'{tag_info}")
            return True
        else:
            print(f"  [FAILED] Could not create post: {error_msg}")
            return False


async def import_all_from_shopify(force_pull: bool = False) -> dict:
    """
    Import all content from Shopify into Supabase.

    Imports in order: categories (blogs), tags, posts (articles).

    Args:
        force_pull: If True, overwrite existing Supabase data.

    Returns:
        dict with results for each content type
    """
    results = {}

    print("=" * 60)
    print("IMPORTING CATEGORIES (BLOGS)")
    print("=" * 60)
    results["categories"] = await import_categories_from_shopify(force_pull)
    print()

    print("=" * 60)
    print("IMPORTING TAGS")
    print("=" * 60)
    results["tags"] = await import_tags_from_shopify(force_pull)
    print()

    print("=" * 60)
    print("IMPORTING POSTS (ARTICLES)")
    print("=" * 60)
    results["posts"] = await import_posts_from_shopify(force_pull)
    print()

    # Final summary
    print("=" * 60)
    print("IMPORT COMPLETE")
    print("=" * 60)
    total_imported = sum(r.get("imported", 0) for r in results.values())
    total_updated = sum(r.get("updated", 0) for r in results.values())
    total_skipped = sum(r.get("skipped", 0) for r in results.values())
    total_errors = sum(len(r.get("errors", [])) for r in results.values())

    print(f"Total: {total_imported} imported, {total_updated} updated, {total_skipped} skipped, {total_errors} errors")

    return results
