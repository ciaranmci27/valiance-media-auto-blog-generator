-- =============================================================================
-- ClutchCaddie Blog System - Complete Schema
-- =============================================================================
-- This file creates all tables needed for the blog system.
-- Run this in your Supabase SQL Editor if setting up a new project.
--
-- Tables created:
--   1. blog_authors     - Author profiles
--   2. blog_categories  - Post categories
--   3. blog_tags        - Post tags
--   4. blog_posts       - Blog posts with JSONB content
--   5. blog_post_tags   - Junction table for post-tag relationships
--
-- =============================================================================

-- =============================================================================
-- 1. BLOG AUTHORS
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.blog_authors (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  slug text NOT NULL,
  name text NOT NULL,
  image text,                              -- Avatar/profile image URL
  bio text,                                -- Author biography
  show_bio boolean DEFAULT true,           -- Whether to display bio on posts
  created_at timestamp with time zone DEFAULT now(),

  -- Constraints
  CONSTRAINT blog_authors_pkey PRIMARY KEY (id),
  CONSTRAINT blog_authors_slug_key UNIQUE (slug)
);

-- Index for slug lookups
CREATE INDEX IF NOT EXISTS idx_blog_authors_slug ON public.blog_authors(slug);

-- Enable RLS
ALTER TABLE public.blog_authors ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Public read access for authors"
  ON public.blog_authors FOR SELECT
  USING (true);

CREATE POLICY "Service role full access for authors"
  ON public.blog_authors FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- =============================================================================
-- 2. BLOG CATEGORIES
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.blog_categories (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  slug text NOT NULL,
  name text NOT NULL,
  description text,                        -- Category description
  image text,                              -- Category header image
  sort_order integer DEFAULT 0,            -- For ordering in navigation
  seo jsonb DEFAULT '{}'::jsonb,           -- SEO metadata: {title, description, keywords}
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),

  -- Constraints
  CONSTRAINT blog_categories_pkey PRIMARY KEY (id),
  CONSTRAINT blog_categories_slug_key UNIQUE (slug)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_blog_categories_slug ON public.blog_categories(slug);
CREATE INDEX IF NOT EXISTS idx_blog_categories_sort ON public.blog_categories(sort_order);

-- Enable RLS
ALTER TABLE public.blog_categories ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Public read access for categories"
  ON public.blog_categories FOR SELECT
  USING (true);

CREATE POLICY "Service role full access for categories"
  ON public.blog_categories FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_blog_categories_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_blog_categories_updated_at ON public.blog_categories;
CREATE TRIGGER trigger_blog_categories_updated_at
  BEFORE UPDATE ON public.blog_categories
  FOR EACH ROW
  EXECUTE FUNCTION update_blog_categories_updated_at();

-- =============================================================================
-- 3. BLOG TAGS
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.blog_tags (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  slug text NOT NULL,
  name text NOT NULL,
  created_at timestamp with time zone DEFAULT now(),

  -- Constraints
  CONSTRAINT blog_tags_pkey PRIMARY KEY (id),
  CONSTRAINT blog_tags_slug_key UNIQUE (slug)
);

-- Index for slug lookups
CREATE INDEX IF NOT EXISTS idx_blog_tags_slug ON public.blog_tags(slug);
CREATE INDEX IF NOT EXISTS idx_blog_tags_name ON public.blog_tags(name);

-- Enable RLS
ALTER TABLE public.blog_tags ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Public read access for tags"
  ON public.blog_tags FOR SELECT
  USING (true);

CREATE POLICY "Service role full access for tags"
  ON public.blog_tags FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- =============================================================================
-- 4. BLOG POSTS
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.blog_posts (
  id uuid NOT NULL DEFAULT gen_random_uuid(),

  -- Core content
  slug text NOT NULL,
  title text NOT NULL,
  excerpt text NOT NULL,                   -- Short description for previews
  content jsonb NOT NULL DEFAULT '[]'::jsonb,  -- Array of content blocks

  -- Relationships
  author_id uuid,
  category_id uuid,

  -- Media
  featured_image text,                     -- Hero image URL
  featured_image_alt text,                 -- Alt text for accessibility

  -- Metadata
  reading_time integer,                    -- Estimated minutes to read
  featured boolean DEFAULT false,          -- Featured on homepage
  exclude_from_search boolean DEFAULT false,
  seo jsonb DEFAULT '{}'::jsonb,           -- SEO: {title, description, keywords, image}

  -- Status
  status text NOT NULL DEFAULT 'draft'::text,

  -- Timestamps
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),

  -- Constraints
  CONSTRAINT blog_posts_pkey PRIMARY KEY (id),
  CONSTRAINT blog_posts_slug_key UNIQUE (slug),
  CONSTRAINT blog_posts_status_check CHECK (status = ANY (ARRAY['draft', 'published', 'archived'])),
  CONSTRAINT blog_posts_author_id_fkey FOREIGN KEY (author_id)
    REFERENCES public.blog_authors(id) ON DELETE SET NULL,
  CONSTRAINT blog_posts_category_id_fkey FOREIGN KEY (category_id)
    REFERENCES public.blog_categories(id) ON DELETE SET NULL
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_blog_posts_slug ON public.blog_posts(slug);
CREATE INDEX IF NOT EXISTS idx_blog_posts_status ON public.blog_posts(status);
CREATE INDEX IF NOT EXISTS idx_blog_posts_featured ON public.blog_posts(featured) WHERE featured = true;
CREATE INDEX IF NOT EXISTS idx_blog_posts_category ON public.blog_posts(category_id);
CREATE INDEX IF NOT EXISTS idx_blog_posts_author ON public.blog_posts(author_id);
CREATE INDEX IF NOT EXISTS idx_blog_posts_created ON public.blog_posts(created_at DESC);

-- Composite index for common listing query (published posts by date)
CREATE INDEX IF NOT EXISTS idx_blog_posts_published_date
  ON public.blog_posts(status, created_at DESC)
  WHERE status = 'published';

-- GIN index for content block searching (optional, for full-text search)
CREATE INDEX IF NOT EXISTS idx_blog_posts_content_gin
  ON public.blog_posts USING gin(content jsonb_path_ops);

-- Enable RLS
ALTER TABLE public.blog_posts ENABLE ROW LEVEL SECURITY;

-- RLS Policies
-- Public can only read published posts
CREATE POLICY "Public read access for published posts"
  ON public.blog_posts FOR SELECT
  USING (status = 'published');

-- Service role has full access (for blog generator and admin)
CREATE POLICY "Service role full access for posts"
  ON public.blog_posts FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_blog_posts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_blog_posts_updated_at ON public.blog_posts;
CREATE TRIGGER trigger_blog_posts_updated_at
  BEFORE UPDATE ON public.blog_posts
  FOR EACH ROW
  EXECUTE FUNCTION update_blog_posts_updated_at();

-- =============================================================================
-- 5. BLOG POST TAGS (Junction Table)
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.blog_post_tags (
  post_id uuid NOT NULL,
  tag_id uuid NOT NULL,

  -- Constraints
  CONSTRAINT blog_post_tags_pkey PRIMARY KEY (post_id, tag_id),
  CONSTRAINT blog_post_tags_post_id_fkey FOREIGN KEY (post_id)
    REFERENCES public.blog_posts(id) ON DELETE CASCADE,
  CONSTRAINT blog_post_tags_tag_id_fkey FOREIGN KEY (tag_id)
    REFERENCES public.blog_tags(id) ON DELETE CASCADE
);

-- Indexes for lookups from both directions
CREATE INDEX IF NOT EXISTS idx_blog_post_tags_post ON public.blog_post_tags(post_id);
CREATE INDEX IF NOT EXISTS idx_blog_post_tags_tag ON public.blog_post_tags(tag_id);

-- Enable RLS
ALTER TABLE public.blog_post_tags ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Public read access for post tags"
  ON public.blog_post_tags FOR SELECT
  USING (true);

CREATE POLICY "Service role full access for post tags"
  ON public.blog_post_tags FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- =============================================================================
-- HELPER VIEWS (Optional)
-- =============================================================================

-- View for published posts with author and category info
CREATE OR REPLACE VIEW public.blog_posts_with_details AS
SELECT
  p.*,
  a.name AS author_name,
  a.slug AS author_slug,
  a.image AS author_image,
  a.bio AS author_bio,
  c.name AS category_name,
  c.slug AS category_slug,
  (
    SELECT array_agg(json_build_object('slug', t.slug, 'name', t.name))
    FROM public.blog_post_tags pt
    JOIN public.blog_tags t ON pt.tag_id = t.id
    WHERE pt.post_id = p.id
  ) AS tags
FROM public.blog_posts p
LEFT JOIN public.blog_authors a ON p.author_id = a.id
LEFT JOIN public.blog_categories c ON p.category_id = c.id;

-- =============================================================================
-- SEED DATA (Optional - Uncomment to create initial data)
-- =============================================================================

/*
-- Create default author for AI-generated content
INSERT INTO public.blog_authors (slug, name, bio, show_bio) VALUES
  ('clutchcaddie-team', 'ClutchCaddie Team', 'Expert golf content from the ClutchCaddie team.', true)
ON CONFLICT (slug) DO NOTHING;

-- Create common categories
INSERT INTO public.blog_categories (slug, name, description, sort_order) VALUES
  ('instruction', 'Instruction', 'Tips and techniques to improve your golf game', 1),
  ('equipment', 'Equipment', 'Golf club reviews, fitting guides, and gear recommendations', 2),
  ('practice', 'Practice', 'Drills, training plans, and practice routines', 3),
  ('mental-game', 'Mental Game', 'Psychology, confidence, and handling pressure on the course', 4),
  ('course-management', 'Course Management', 'Strategy, shot selection, and playing smarter golf', 5)
ON CONFLICT (slug) DO NOTHING;

-- Create common tags
INSERT INTO public.blog_tags (slug, name) VALUES
  ('beginner', 'Beginner'),
  ('intermediate', 'Intermediate'),
  ('advanced', 'Advanced'),
  ('driver', 'Driver'),
  ('irons', 'Irons'),
  ('wedges', 'Wedges'),
  ('putting', 'Putting'),
  ('chipping', 'Chipping'),
  ('bunker', 'Bunker Play'),
  ('slice', 'Slice'),
  ('hook', 'Hook'),
  ('swing-mechanics', 'Swing Mechanics'),
  ('grip', 'Grip'),
  ('stance', 'Stance'),
  ('tempo', 'Tempo'),
  ('distance', 'Distance'),
  ('accuracy', 'Accuracy'),
  ('consistency', 'Consistency'),
  ('short-game', 'Short Game'),
  ('long-game', 'Long Game'),
  ('warm-up', 'Warm-Up'),
  ('fitness', 'Fitness'),
  ('flexibility', 'Flexibility'),
  ('mental-game', 'Mental Game'),
  ('pressure', 'Pressure'),
  ('confidence', 'Confidence'),
  ('course-strategy', 'Course Strategy'),
  ('club-fitting', 'Club Fitting'),
  ('ball-flight', 'Ball Flight')
ON CONFLICT (slug) DO NOTHING;
*/

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Run these to verify tables were created correctly:

-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public' AND table_name LIKE 'blog_%';

-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'blog_posts' ORDER BY ordinal_position;

-- SELECT indexname FROM pg_indexes WHERE tablename LIKE 'blog_%';

-- SELECT policyname, tablename FROM pg_policies WHERE tablename LIKE 'blog_%';
