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
python generator.py --backfill-images              # Process 1 post
python generator.py --backfill-images --count 10   # Process up to 10 posts
```

Requires `ENABLE_IMAGE_GENERATION=true` and `GEMINI_API_KEY` in `.env`.

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
```

### Check Sync Status
```bash
python generator.py --shopify-status              # Post sync status
python generator.py --shopify-status-categories   # Category sync status
```

---

## Common Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--verbose` | `-v` | Print detailed progress and tool calls |
| `--count N` | `-c N` | Number of items to process |
| `--force` | | Force sync even if already up-to-date |

---

## Environment Variables

Key variables that affect CLI behavior:

| Variable | Effect |
|----------|--------|
| `BLOGS_PER_RUN` | Default `--count` value (default: 1) |
| `DEFAULT_STATUS` | Status for new posts (`draft`, `published`) |
| `ENABLE_IMAGE_GENERATION` | Enables `--backfill-images` command |
| `ENABLE_SHOPIFY_SYNC` | Enables all `--shopify-*` commands |

See [configuration.md](../configuration.md) for full reference.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (config, sync failed, generation failed) |
