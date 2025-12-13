-- =============================================================================
-- Shopify Sync Schema Additions
-- =============================================================================
-- Run this migration to add Shopify sync tracking columns to your existing tables.
-- This enables one-way synchronization from Supabase to Shopify's blog CMS.

-- Add Shopify tracking to blog_categories
-- Maps Supabase categories to Shopify Blogs
ALTER TABLE public.blog_categories
ADD COLUMN IF NOT EXISTS shopify_blog_gid TEXT;

ALTER TABLE public.blog_categories
ADD COLUMN IF NOT EXISTS shopify_synced_at TIMESTAMPTZ;

COMMENT ON COLUMN public.blog_categories.shopify_blog_gid IS 'Shopify Blog global ID (e.g., gid://shopify/Blog/123456789)';
COMMENT ON COLUMN public.blog_categories.shopify_synced_at IS 'Timestamp of last successful sync to Shopify';

-- Add Shopify tracking to blog_posts
-- Maps Supabase posts to Shopify Articles
ALTER TABLE public.blog_posts
ADD COLUMN IF NOT EXISTS shopify_article_id TEXT;

ALTER TABLE public.blog_posts
ADD COLUMN IF NOT EXISTS shopify_synced_at TIMESTAMPTZ;

ALTER TABLE public.blog_posts
ADD COLUMN IF NOT EXISTS shopify_sync_error TEXT;

COMMENT ON COLUMN public.blog_posts.shopify_article_id IS 'Shopify Article global ID (e.g., gid://shopify/Article/123456789)';
COMMENT ON COLUMN public.blog_posts.shopify_synced_at IS 'Timestamp of last successful sync to Shopify';
COMMENT ON COLUMN public.blog_posts.shopify_sync_error IS 'Error message from last failed sync attempt';

-- Index for finding posts that need syncing
-- A post needs sync if:
-- 1. shopify_article_id IS NULL (never synced), OR
-- 2. updated_at > shopify_synced_at (updated since last sync)
CREATE INDEX IF NOT EXISTS idx_blog_posts_shopify_sync
ON public.blog_posts(shopify_synced_at, updated_at);

-- Index for finding unsynced categories
CREATE INDEX IF NOT EXISTS idx_blog_categories_shopify_sync
ON public.blog_categories(shopify_blog_gid)
WHERE shopify_blog_gid IS NULL;

-- =============================================================================
-- Helper Views (Optional)
-- =============================================================================

-- View to easily see posts needing sync
CREATE OR REPLACE VIEW public.v_posts_needing_shopify_sync AS
SELECT
    id,
    slug,
    title,
    status,
    updated_at,
    shopify_synced_at,
    shopify_article_id,
    CASE
        WHEN shopify_article_id IS NULL THEN 'never_synced'
        WHEN updated_at > shopify_synced_at THEN 'stale'
        ELSE 'synced'
    END as sync_status
FROM public.blog_posts
WHERE shopify_article_id IS NULL
   OR updated_at > COALESCE(shopify_synced_at, '1970-01-01'::timestamptz)
ORDER BY updated_at DESC;

-- View to see category sync status
CREATE OR REPLACE VIEW public.v_categories_shopify_status AS
SELECT
    id,
    slug,
    name,
    shopify_blog_gid,
    shopify_synced_at,
    CASE
        WHEN shopify_blog_gid IS NULL THEN 'not_synced'
        ELSE 'synced'
    END as sync_status
FROM public.blog_categories
ORDER BY sort_order, name;
