# Autonomous Blog Generator

An AI-powered blog generation system that uses Claude to autonomously create high-quality, SEO-optimized content. The system connects to Supabase, processes topics from a queue, and outputs structured blog posts.

## Important: Customization Required

**This is not a plug-and-play solution.** This generator uses a **content block system** where posts are stored as JSON arrays, not HTML. Your frontend must be built to render these blocks (unless you are using Shopify).

This project serves as a **reference implementation**. It ships configured for golf content as a working example — customize it for your niche.

## Features

- **Content Block System** - Generates posts as structured JSON blocks (19 customizable block types)
- **Autonomous Mode** - Process blog ideas from a queue without manual intervention
- **AI Image Generation** - Optional featured images via Gemini
- **Internal Link Building** - Automatic internal linking with URL validation
- **Shopify Sync** - One-way sync to Shopify's blog CMS
- **WordPress Sync** - One-way sync to WordPress via REST API
- **SEO Optimized** - Generates titles, excerpts, slugs, and keyword metadata
- **Cost Optimized** - Prompt caching reduces token usage by ~50%

## How It Works

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  IDEA QUEUE     │     │     CLAUDE      │     │    SUPABASE     │
│  (blog_ideas)   │ ──► │   (AI Agent)    │ ──► │   (blog_posts)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                         ┌──────────────┴──────────────┐
                                         ▼ (optional)                  ▼ (optional)
                                 ┌─────────────────┐           ┌─────────────────┐
                                 │    SHOPIFY      │           │   WORDPRESS     │
                                 │   (Articles)    │           │    (Posts)      │
                                 └─────────────────┘           └─────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:
```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyxxxxx
DEFAULT_AUTHOR_SLUG=your-author-slug
```

### 3. Set Up Database

Run the SQL files in your Supabase SQL Editor:
- `schema/blog_tables.sql` - Core tables
- `schema/blog_ideas.sql` - Queue table

See [Database Setup](docs/database-setup.md) for full details.

### 4. Add Ideas to Queue

**Option A: Web Tool (Recommended)**

Use the [Blog Ideas Refiner](https://blog-ideas.valiancemedia.com) — a simple web app that lets you:
- Paste ideas in any format (bullet points, numbered lists, plain text)
- Automatically remove duplicates and similar topics
- Check against your existing ideas to avoid repeats
- Preview everything before adding to your database

No coding required. Just paste your ideas, enter your Supabase credentials, and click upload.

**Option B: Direct SQL**

For developers, you can insert ideas directly:

```sql
INSERT INTO blog_ideas (topic, description, priority) VALUES
  ('Your Topic Here', 'Guidance for the AI', 90);
```

### 5. Generate Content

```bash
python generator.py --autonomous
```

## Usage

```bash
# Autonomous mode - process from queue
python generator.py --autonomous
python generator.py -a --count 5

# Manual mode - specific topic
python generator.py "Your topic here"

# Check queue status
python generator.py --status

# Backfill images for existing posts
python generator.py --backfill-images --count 10
python generator.py --backfill-images-all

# Clean up or refresh bad featured images
python generator.py --cleanup-image post-slug      # Remove image by slug
python generator.py --cleanup-image-id <uuid>      # Remove image by post ID
python generator.py --refresh-image post-slug      # Replace image by slug
python generator.py --refresh-image-id <uuid>      # Replace image by post ID

# Backfill internal links for existing posts
python generator.py --backfill-links --count 5
python generator.py --backfill-links-all
python generator.py --backfill-links-id <uuid>
python generator.py --backfill-links-slug post-slug

# Clean up internal links
python generator.py --cleanup-links post-slug
python generator.py --cleanup-links-id <uuid>
python generator.py --cleanup-links-all

# Remove a single link by its blog_post_links table ID
python generator.py --remove-link <link-uuid>
```

## Shopify Sync

Optionally sync all content to a Shopify store:

```bash
# Sync categories first
python generator.py --shopify-sync-categories

# Sync all posts
python generator.py --shopify-sync-all

# Check sync status
python generator.py --shopify-status

# Import existing Shopify content into Supabase
python generator.py --shopify-import-all
python generator.py --shopify-import-post "article-slug"
```

See [Getting Started with Shopify](docs/setup/shopify/getting-started-with-shopify.md) for setup instructions.

## WordPress Sync

Optionally sync all content to a WordPress site:

```bash
# Sync categories first
python generator.py --wordpress-sync-categories

# Sync all posts
python generator.py --wordpress-sync-all

# Check sync status
python generator.py --wordpress-status

# Import existing WordPress categories into Supabase
python generator.py --wordpress-import-categories
```

See [Getting Started with WordPress](docs/setup/wordpress/getting-started-with-wordpress.md) for setup instructions.

## Project Structure

```
├── generator.py              # Main entry point
├── config.py                 # Configuration
├── tools/                    # Claude tool definitions
│   ├── query_tools.py        # Read from Supabase
│   ├── write_tools.py        # Write to Supabase
│   ├── idea_tools.py         # Queue management
│   ├── image_tools.py        # AI image generation
│   ├── link_tools.py         # Internal link building
│   ├── shopify_tools.py      # Shopify API
│   ├── shopify_sync.py       # Shopify CLI handlers
│   ├── wordpress_tools.py    # WordPress REST API
│   └── wordpress_sync.py     # WordPress CLI handlers
├── prompts/
│   ├── system_prompt.md      # Universal instructions
│   └── niche/                # Niche-specific prompts
├── schema/                   # SQL schemas
└── docs/                     # Documentation
```

## Documentation

### Getting Started Guides

| Guide | Description |
|-------|-------------|
| [Getting Started with React](docs/setup/getting-started-with-react.md) | Render content blocks in React |
| [Getting Started with Shopify](docs/setup/shopify/getting-started-with-shopify.md) | Sync content to Shopify |
| [Getting Started with WordPress](docs/setup/wordpress/getting-started-with-wordpress.md) | Sync content to WordPress |
| [How to Use](docs/setup/how-to-use.md) | All CLI commands and options |
| [How to Automate](docs/setup/how-to-automate.md) | GitHub Actions workflow setup |

### Reference

| Guide | Description |
|-------|-------------|
| [Content Blocks](docs/content-blocks.md) | Block type reference and customization |
| [Niche Customization](docs/niche-customization.md) | Creating niche-specific prompts |
| [Database Setup](docs/database-setup.md) | Supabase schema and queue management |
| [Configuration](docs/configuration.md) | All environment variables |

## Configuration

Essential variables (see [full reference](docs/configuration.md)):

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key |
| `DEFAULT_AUTHOR_SLUG` | Yes | Author slug for posts |
| `NICHE_PROMPT_PATH` | No | Path to niche prompt |
| `ENABLE_IMAGE_GENERATION` | No | Enable Gemini images |
| `ENABLE_LINK_BUILDING` | No | Enable internal link building |
| `ENABLE_SHOPIFY_SYNC` | No | Enable Shopify sync |
| `ENABLE_WORDPRESS_SYNC` | No | Enable WordPress sync |

## Cost Estimation

Using Claude Sonnet 4.5 with prompt caching:
- $0.30~ per blog post (without image)
- $0.45~ per blog post (with image)
- Prompt caching reduces costs by ~50%

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Built with [Claude](https://www.anthropic.com/claude) by Anthropic and [Supabase](https://supabase.com/).
