# CLI Usage Reference

Complete list of commands for the blog generator.

## Quick Examples

```bash
# Generate a single post
python generator.py "How to improve your golf swing"

# Process 5 posts from the queue
python generator.py --autonomous --count 5

# Check what's in the queue
python generator.py --status

# Sync everything to Shopify
python generator.py --shopify-sync-categories
python generator.py --shopify-sync-all

# Sync everything to WordPress
python generator.py --wordpress-sync-categories
python generator.py --wordpress-sync-all
```

---

## Content Generation

### Manual Mode
Generate a post about a specific topic.

```bash
python generator.py "Your topic here"
python generator.py "Best practices for React hooks" --verbose
```

### Autonomous Mode
Process ideas from the `blog_ideas` queue.

```bash
python generator.py --autonomous              # Process 1 idea (default)
python generator.py -a --count 5              # Process up to 5 ideas
python generator.py -a -c 10 --verbose        # Process 10 with logging
```

### Batch Mode
Generate posts from a text file (one topic per line).

```bash
python generator.py --batch topics.txt
```

### Interactive Mode
REPL-style interface for generating posts.

```bash
python generator.py --interactive
```

Commands inside interactive mode:
- Type a topic to generate a post
- `status` - Show queue status
- `auto` - Process one idea from queue
- `quit` - Exit

---

## Queue Management

### Check Status
```bash
python generator.py --status
python generator.py -s
```

Shows pending, in-progress, completed, and failed ideas.

### Add Ideas to Queue
```sql
-- In Supabase SQL Editor
INSERT INTO blog_ideas (topic, description, priority) VALUES
  ('Your Topic', 'Instructions for the AI', 80);
```

---

## Image Generation

### Backfill Missing Images
Generate featured images for posts that don't have them.

```bash
python generator.py --backfill-images              # Process 1 post (default)
python generator.py --backfill-images --count 10   # Process up to 10 posts
python generator.py --backfill-images-all          # Process ALL posts without images
```

Requires `ENABLE_IMAGE_GENERATION=true` and `GEMINI_API_KEY` in `.env`.

### Clean Up Bad Images
Remove a featured image from a post (clears database fields and deletes from storage).

```bash
python generator.py --cleanup-image "post-slug"    # Clean up by slug
python generator.py --cleanup-image-id "uuid"      # Clean up by post ID
```

The cleanup process:
1. Sets `featured_image` and `featured_image_alt` to NULL in the database
2. Deletes the image file from Supabase storage bucket

### Refresh Images (Cleanup + Generate New)
Replace a bad featured image with a new one in a single command.

```bash
python generator.py --refresh-image "post-slug"    # Replace by slug
python generator.py --refresh-image-id "uuid"      # Replace by post ID
python generator.py --refresh-image "post-slug" -v # With verbose output
```

The refresh process:
1. Cleans up the existing image (DB + storage)
2. Generates a new image using the post's title and excerpt
3. Updates the post with the new image URL

**Typical workflow for bad images:**
```bash
# Option 1: Replace immediately with new image
python generator.py --refresh-image my-bad-post

# Option 2: Remove now, backfill later
python generator.py --cleanup-image my-bad-post
python generator.py --backfill-images --count 1
```

---

## Link Building

When `ENABLE_LINK_BUILDING=true`, the generator automatically:
- **Internal links**: Added during post creation AND can be backfilled to existing posts
- **External links**: Added during post creation only (requires topic research)

### Backfill Internal Links
Add internal links to posts that have fewer than recommended for your catalog size.

```bash
python generator.py --backfill-links                    # Process 1 post (default)
python generator.py --backfill-links --count 5          # Process up to 5 posts
python generator.py --backfill-links-all                # Process ALL posts that need links
python generator.py --backfill-links-id "uuid"          # Process a specific post by ID
python generator.py --backfill-links-slug post-slug     # Process a specific post by slug
python generator.py --backfill-links --verbose          # Show detailed progress
```

The backfill process:
1. Calculates realistic link targets based on catalog size (not just word count)
2. Finds posts with fewer internal links than the adjusted target
3. Identifies related posts and natural phrases to link
4. Safely inserts links by wrapping exact phrases (no content modification)
5. Validates all URLs before applying

**Note:** Backfill only handles internal links. External links require topic research and are added during initial post creation.

Requires `ENABLE_LINK_BUILDING=true` and the `blog_post_links` table.

### Clean Up Internal Links
Remove internal links from posts (e.g., to fix bad links before re-running backfill).

```bash
python generator.py --cleanup-links "post-slug"     # Clean up by slug
python generator.py --cleanup-links-id "uuid"       # Clean up by post ID
python generator.py --cleanup-links-all             # Clean up ALL posts (requires confirmation)
```

The cleanup process:
1. Strips all internal `<a href="/...">` tags from post content
2. Preserves the anchor text (link text remains, just not linked)
3. Deletes matching records from the `blog_post_links` table

### Remove a Single Link
Remove a specific link by its `blog_post_links` table ID (useful for removing individual bad links without affecting others).

```bash
python generator.py --remove-link "uuid"       # Remove single link by its ID
```

This command:
1. Looks up the link record to find the URL and associated post
2. Removes the specific `<a>` tag from the post content (preserves anchor text)
3. Deletes the link record from the `blog_post_links` table

**Typical workflow to fix bad links:**
```bash
# 1. Remove the bad links
python generator.py --cleanup-links-all

# 2. Re-run backfill with improved semantic matching
python generator.py --backfill-links-all --verbose
```

---

## Shopify Sync

Requires `ENABLE_SHOPIFY_SYNC=true` in `.env`.

### Sync Categories
Categories become Shopify Blogs.

```bash
python generator.py --shopify-sync-categories                  # Sync all
python generator.py --shopify-sync-category "category-slug"    # Sync one
python generator.py --shopify-sync-categories --force          # Force re-sync
```

### Sync Posts
Posts become Shopify Articles.

```bash
python generator.py --shopify-sync-all                 # Sync all posts
python generator.py --shopify-sync "post-slug"         # Sync by slug
python generator.py --shopify-sync-id "uuid"           # Sync by ID
python generator.py --shopify-sync-recent 10           # Sync 10 most recent
python generator.py --shopify-sync-all --force         # Force re-sync all

# Sync multiple posts at once (skips missing, shows summary)
python generator.py --shopify-sync-slugs "slug-1,slug-2,slug-3" --force
```

**Note:** `--shopify-sync-all` requires confirmation before proceeding to prevent accidental overwrites.

**Tip:** Use `--shopify-sync-slugs` for batch operations - it continues on missing posts and gives a summary at the end.

### Check Sync Status
```bash
python generator.py --shopify-status              # Post sync status
python generator.py --shopify-status-categories   # Category sync status
```

### Import from Shopify
Import existing content from Shopify into Supabase.

```bash
# Import all content at once
python generator.py --shopify-import-all                      # Categories, tags, posts

# Import content types individually
python generator.py --shopify-import-categories               # Shopify Blogs → categories
python generator.py --shopify-import-tags                     # Extract tags from articles
python generator.py --shopify-import-posts                    # Shopify Articles → posts

# Import a single post by slug (always overwrites)
python generator.py --shopify-import-post "article-slug"

# Force overwrite existing Supabase data
python generator.py --shopify-import-all --force-pull
python generator.py --shopify-import-posts --force-pull
```

**Note:** Bulk import operations (`--shopify-import-all`, `--shopify-import-posts --force-pull`) require confirmation before proceeding.

---

## WordPress Sync

Requires `ENABLE_WORDPRESS_SYNC=true` in `.env`.

### Sync Categories
Categories become WordPress Categories.

```bash
python generator.py --wordpress-sync-categories                  # Sync all
python generator.py --wordpress-sync-category "category-slug"    # Sync one
python generator.py --wordpress-sync-categories --force          # Force re-sync
```

### Sync Posts
Posts become WordPress Posts.

```bash
python generator.py --wordpress-sync-all                 # Sync all posts
python generator.py --wordpress-sync "post-slug"         # Sync by slug
python generator.py --wordpress-sync-id "uuid"           # Sync by ID
python generator.py --wordpress-sync-recent 10           # Sync 10 most recent
python generator.py --wordpress-sync-all --force         # Force re-sync all
```

### Check Sync Status
```bash
python generator.py --wordpress-status              # Post sync status
python generator.py --wordpress-status-categories   # Category sync status
```

### Import from WordPress
Import existing categories from WordPress into Supabase.

```bash
python generator.py --wordpress-import-categories               # Import, skip existing
python generator.py --wordpress-import-categories --force-pull  # Overwrite existing
```

---

## Common Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--verbose` | `-v` | Print detailed progress and tool calls |
| `--count N` | `-c N` | Number of items to process |
| `--force` | | Force sync even if already up-to-date (push to CMS) |
| `--force-pull` | | Force overwrite Supabase with CMS data (import commands) |

---

## Environment Variables

Key variables that affect CLI behavior:

| Variable | Effect |
|----------|--------|
| `BLOGS_PER_RUN` | Default `--count` value (default: 1) |
| `DEFAULT_STATUS` | Status for new posts (`draft`, `published`) |
| `ENABLE_IMAGE_GENERATION` | Enables `--backfill-images` command |
| `ENABLE_LINK_BUILDING` | Enables internal linking and `--backfill-links` |
| `ENABLE_SHOPIFY_SYNC` | Enables all `--shopify-*` commands |
| `ENABLE_WORDPRESS_SYNC` | Enables all `--wordpress-*` commands |

See [configuration.md](../configuration.md) for full reference.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (config, sync failed, generation failed) |
