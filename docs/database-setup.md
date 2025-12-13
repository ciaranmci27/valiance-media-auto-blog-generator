# Database Setup

This guide covers setting up the required Supabase tables for the blog generator.

## Required Tables

The generator requires these tables:

| Table | Purpose |
|-------|---------|
| `blog_posts` | Stores generated blog posts |
| `blog_categories` | Content categories |
| `blog_tags` | Tags for posts |
| `blog_post_tags` | Many-to-many relationship |
| `blog_authors` | Author profiles |
| `blog_ideas` | Generation queue |

## Quick Setup

Run the SQL files in your Supabase SQL Editor:

```bash
# 1. Create core blog tables
schema/blog_tables.sql

# 2. Create the ideas queue
schema/blog_ideas.sql

# 3. (Optional) Enable image storage
schema/storage_bucket.sql

# 4. (Optional) Enable Shopify sync
schema/shopify_sync.sql
```

## Table Schemas

### blog_posts

```sql
CREATE TABLE blog_posts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  excerpt TEXT NOT NULL,
  content JSONB NOT NULL DEFAULT '[]',

  author_id UUID REFERENCES blog_authors(id),
  category_id UUID REFERENCES blog_categories(id),

  featured_image TEXT,
  featured_image_alt TEXT,
  reading_time INTEGER,
  featured BOOLEAN DEFAULT false,

  seo JSONB DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'draft',

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  scheduled_at TIMESTAMPTZ,

  -- Shopify sync fields (optional)
  shopify_article_id TEXT,
  shopify_synced_at TIMESTAMPTZ,
  shopify_sync_error TEXT,

  CONSTRAINT status_check CHECK (status IN ('draft', 'published', 'scheduled', 'archived'))
);
```

### blog_categories

```sql
CREATE TABLE blog_categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  image TEXT,
  sort_order INTEGER DEFAULT 0,
  seo JSONB DEFAULT '{}',

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- Shopify sync fields (optional)
  shopify_blog_gid TEXT,
  shopify_synced_at TIMESTAMPTZ
);
```

### blog_tags

```sql
CREATE TABLE blog_tags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### blog_post_tags

```sql
CREATE TABLE blog_post_tags (
  post_id UUID NOT NULL REFERENCES blog_posts(id) ON DELETE CASCADE,
  tag_id UUID NOT NULL REFERENCES blog_tags(id) ON DELETE CASCADE,
  PRIMARY KEY (post_id, tag_id)
);
```

### blog_authors

```sql
CREATE TABLE blog_authors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  image TEXT,
  bio TEXT,
  show_bio BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### blog_ideas (Queue)

```sql
CREATE TABLE blog_ideas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  topic TEXT NOT NULL,
  description TEXT,
  priority INTEGER DEFAULT 50,
  target_category_slug TEXT,
  target_tags TEXT[],
  status TEXT DEFAULT 'pending',
  claimed_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  result_post_id UUID REFERENCES blog_posts(id),
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),

  CONSTRAINT status_check CHECK (status IN ('pending', 'in_progress', 'completed', 'failed'))
);
```

## Managing the Queue

### Add Ideas

```sql
-- Single idea
INSERT INTO blog_ideas (topic, description, priority)
VALUES ('My Topic', 'Description here', 80);

-- With target category
INSERT INTO blog_ideas (topic, description, priority, target_category_slug)
VALUES ('Golf Tips', 'Tips for beginners', 90, 'instruction');

-- Bulk insert
INSERT INTO blog_ideas (topic, description, priority) VALUES
  ('Topic 1', 'Description 1', 85),
  ('Topic 2', 'Description 2', 80),
  ('Topic 3', 'Description 3', 75);
```

### View Queue Status

```sql
-- Pending ideas by priority
SELECT topic, priority, created_at
FROM blog_ideas
WHERE status = 'pending'
ORDER BY priority DESC;

-- Failed ideas
SELECT topic, error_message, created_at
FROM blog_ideas
WHERE status = 'failed';

-- Completed today
SELECT topic, completed_at
FROM blog_ideas
WHERE status = 'completed'
AND completed_at > NOW() - INTERVAL '24 hours';
```

### Retry Failed Ideas

```sql
-- Retry a specific idea
UPDATE blog_ideas
SET status = 'pending', error_message = NULL, claimed_at = NULL
WHERE id = 'uuid-here';

-- Retry all failed ideas
UPDATE blog_ideas
SET status = 'pending', error_message = NULL, claimed_at = NULL
WHERE status = 'failed';
```

### Reset Stuck Ideas

If the generator crashes, ideas may be stuck in `in_progress`:

```sql
-- Reset stuck ideas (older than 30 minutes)
UPDATE blog_ideas
SET status = 'pending', claimed_at = NULL
WHERE status = 'in_progress'
AND claimed_at < NOW() - INTERVAL '30 minutes';
```

## Row Level Security (RLS)

Enable RLS for security:

```sql
-- Enable RLS on all tables
ALTER TABLE blog_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE blog_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE blog_tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE blog_authors ENABLE ROW LEVEL SECURITY;
ALTER TABLE blog_ideas ENABLE ROW LEVEL SECURITY;

-- Public read access for published content
CREATE POLICY "Public read published posts"
  ON blog_posts FOR SELECT
  USING (status = 'published');

CREATE POLICY "Public read categories"
  ON blog_categories FOR SELECT
  USING (true);

-- Service role full access (for the generator)
CREATE POLICY "Service role full access"
  ON blog_posts FOR ALL
  TO service_role
  USING (true) WITH CHECK (true);
```

## Indexes

Recommended indexes for performance:

```sql
-- Posts
CREATE INDEX idx_posts_status ON blog_posts(status);
CREATE INDEX idx_posts_category ON blog_posts(category_id);
CREATE INDEX idx_posts_created ON blog_posts(created_at DESC);
CREATE INDEX idx_posts_slug ON blog_posts(slug);

-- Ideas queue
CREATE INDEX idx_ideas_status_priority ON blog_ideas(status, priority DESC);
CREATE INDEX idx_ideas_status ON blog_ideas(status);

-- Tags
CREATE INDEX idx_post_tags_post ON blog_post_tags(post_id);
CREATE INDEX idx_post_tags_tag ON blog_post_tags(tag_id);
```

## Seed Data

Create initial data for the generator:

```sql
-- Create default author
INSERT INTO blog_authors (slug, name, bio) VALUES
  ('staff-writer', 'Staff Writer', 'Expert content from our team.');

-- Create categories
INSERT INTO blog_categories (slug, name, description, sort_order) VALUES
  ('getting-started', 'Getting Started', 'Beginner guides', 1),
  ('tutorials', 'Tutorials', 'Step-by-step tutorials', 2),
  ('tips', 'Tips & Tricks', 'Quick tips and advice', 3);

-- Create common tags
INSERT INTO blog_tags (slug, name) VALUES
  ('beginner', 'Beginner'),
  ('intermediate', 'Intermediate'),
  ('advanced', 'Advanced');
```
