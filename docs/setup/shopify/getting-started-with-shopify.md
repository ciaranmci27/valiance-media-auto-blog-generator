# Getting Started with Shopify

Sync your blog content to Shopify.

## Prerequisites

### 1. Set Up Supabase

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** in your dashboard
3. Run the schema files in order:

```
schema/blog_tables.sql    → Core tables (posts, categories, authors, tags)
schema/blog_ideas.sql     → Generation queue
schema/shopify_sync.sql   → Shopify tracking columns
```

### 2. Create an Author

```sql
INSERT INTO blog_authors (slug, name, bio) VALUES
  ('staff-writer', 'Staff Writer', 'Expert content from our team.');
```

### 3. Configure Base Environment

```bash
cp .env.example .env
```

Edit `.env` with your Supabase credentials:
```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyxxxxx
DEFAULT_AUTHOR_SLUG=staff-writer
```

---

## Shopify Setup

### 4. Create a Shopify App

1. Go to [developers.shopify.com](https://developers.shopify.com)
2. Click **Apps** → **Create app**
3. Choose **"Build app for users in your organization"**
4. Name it "Blog Sync" and create it

### 5. Configure API Access

1. Go to **Configuration** → **API access**
2. Add these scopes:
   - `read_content`
   - `write_content`
3. Click **Save**

### 6. Install on Your Store

1. Go to **Distribution**
2. Click **Install app** on your store
3. Go to **Settings** and copy your **Client ID** and **Client Secret**

### 7. Add Shopify Config to .env

```env
ENABLE_SHOPIFY_SYNC=true
SHOPIFY_STORE=your-store-name
SHOPIFY_CLIENT_ID=your-client-id
SHOPIFY_CLIENT_SECRET=your-client-secret
SHOPIFY_DEFAULT_AUTHOR=Staff Writer
SHOPIFY_SYNC_ON_PUBLISH=true
```

### 8. Sync Your Content

```bash
pip install -r requirements.txt

# Sync categories first (creates Shopify Blogs)
python generator.py --shopify-sync-categories

# Sync all posts (creates Shopify Articles)
python generator.py --shopify-sync-all
```

### Alternative: Import Existing Content from Shopify

If you already have content in Shopify and want to import it into Supabase:

```bash
# Import everything at once (categories/blogs, tags, posts/articles)
python generator.py --shopify-import-all

# Or import individually:
python generator.py --shopify-import-categories
python generator.py --shopify-import-tags
python generator.py --shopify-import-posts

# Import a single post by slug (always overwrites Supabase data)
python generator.py --shopify-import-post "article-slug"
```

**With `--force-pull`**: Overwrites existing Supabase data with Shopify data:
```bash
python generator.py --shopify-import-all --force-pull
```

This is useful when:
- Setting up the generator with an existing Shopify store
- You want Supabase to mirror your existing Shopify content
- You made changes in Shopify and want to pull them into Supabase
- You need to restore a specific post from Shopify (`--shopify-import-post`)

**Note:** Bulk import operations require confirmation before proceeding to prevent accidental data loss.

**What gets imported:**
- **Categories**: Shopify Blogs → `blog_categories` table
- **Tags**: Extracted from all Shopify Articles → `blog_tags` table
- **Posts**: Shopify Articles → `blog_posts` table (with HTML content preserved)

**Note:** Shopify doesn't have a separate Tags API. Tags are extracted from all articles during import. Post content is stored as HTML. To convert to structured content blocks, you would need to manually edit posts in your frontend.

---

## Done!

Your content is now in Shopify. New posts will auto-sync when created (if `SHOPIFY_SYNC_ON_PUBLISH=true`).

---

## Quick Reference

### Check Status
```bash
python generator.py --shopify-status
python generator.py --shopify-status-categories
```

### Sync Commands
```bash
# Sync everything
python generator.py --shopify-sync-categories
python generator.py --shopify-sync-all

# Sync specific items
python generator.py --shopify-sync "post-slug"
python generator.py --shopify-sync-category "category-slug"

# Sync multiple posts (skips missing, shows summary)
python generator.py --shopify-sync-slugs "slug-1,slug-2,slug-3" --force

# Force re-sync
python generator.py --shopify-sync-all --force
```

### Import Commands
```bash
# Import all content from Shopify
python generator.py --shopify-import-all

# Import a single post by slug (overwrites Supabase)
python generator.py --shopify-import-post "article-slug"

# Force overwrite existing data
python generator.py --shopify-import-posts --force-pull
```

### How Status Maps

| Supabase | Shopify |
|----------|---------|
| `draft` | Hidden |
| `archived` | Hidden |
| `published` | Visible |
| `scheduled` | Scheduled |

---

## Theme Setup (Optional)

### Add Content Styling

Copy the CSS from [shopify-theme-css.md](shopify-theme-css.md) into your theme's CSS file.

### Enable SEO Meta Descriptions

Shopify's API can't set meta descriptions directly. Update your theme's `layout/theme.liquid`:

Find this line:
```liquid
<meta name="description" content="{{ page_description | escape }}">
```

Replace with:
```liquid
{%- if template.name == 'article' and article.excerpt != blank -%}
  <meta name="description" content="{{ article.excerpt | strip_html | truncate: 160 | escape }}">
{%- elsif page_description != blank -%}
  <meta name="description" content="{{ page_description | escape }}">
{%- endif -%}
```

This uses the article excerpt (synced from Supabase) as the meta description.

---

## Troubleshooting

**"Shopify credentials not configured"**
→ Check your `.env` has all Shopify variables set

**Posts not appearing**
→ Check `--shopify-status`. Drafts sync but are hidden in Shopify.

**Duplicate blogs created**
→ Delete duplicates in Shopify admin, then run `--shopify-sync-categories --force`

---

## Next Steps

- See [database-setup.md](../database-setup.md) for queue management
- See [configuration.md](../configuration.md) for all environment variables
- See [shopify-seo-setup.md](shopify-seo-setup.md) for advanced SEO metafields
