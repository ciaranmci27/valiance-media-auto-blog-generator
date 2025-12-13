# Autonomous Blog Generator

An AI-powered blog generation system that uses Claude to autonomously create high-quality, SEO-optimized content. The system connects to Supabase, processes topics from a queue, and outputs structured blog posts.

## Important: Customization Required

**This is not a plug-and-play solution.** This generator uses a **content block system** where posts are stored as JSON arrays, not HTML. Your frontend must be built to render these blocks.

This project serves as a **reference implementation**. It ships configured for golf content as a working example — customize it for your niche.

## Features

- **Content Block System** - Generates posts as structured JSON blocks (19 customizable block types)
- **Autonomous Mode** - Process blog ideas from a queue without manual intervention
- **AI Image Generation** - Optional featured images via Gemini
- **Shopify Sync** - One-way sync to Shopify's blog CMS
- **SEO Optimized** - Generates titles, excerpts, slugs, and keyword metadata
- **Cost Optimized** - Prompt caching reduces token usage by ~50%

## How It Works

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  IDEA QUEUE     │     │     CLAUDE      │     │    SUPABASE     │
│  (blog_ideas)   │ ──► │   (AI Agent)    │ ──► │   (blog_posts)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼ (optional)
                                                ┌─────────────────┐
                                                │    SHOPIFY      │
                                                │   (Articles)    │
                                                └─────────────────┘
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
python generator.py --backfill-images
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
```

See [Getting Started with Shopify](docs/setup/getting-started-with-shopify.md) for setup instructions.

## Project Structure

```
├── generator.py              # Main entry point
├── config.py                 # Configuration
├── tools/                    # Claude tool definitions
│   ├── query_tools.py        # Read from Supabase
│   ├── write_tools.py        # Write to Supabase
│   ├── idea_tools.py         # Queue management
│   ├── image_tools.py        # AI image generation
│   ├── shopify_tools.py      # Shopify API
│   └── shopify_sync.py       # Shopify CLI handlers
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
| [Getting Started with Shopify](docs/setup/getting-started-with-shopify.md) | Sync content to Shopify |
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
| `ENABLE_SHOPIFY_SYNC` | No | Enable Shopify sync |

## Cost Estimation

Using Claude Sonnet 4.5 with prompt caching:
- ~$0.15-0.25 per blog post
- Prompt caching reduces costs by ~50%

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Built with [Claude](https://www.anthropic.com/claude) by Anthropic and [Supabase](https://supabase.com/).
