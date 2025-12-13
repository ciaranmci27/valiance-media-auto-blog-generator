# Configuration Reference

All configuration is done through environment variables. Copy `.env.example` to `.env` and customize.

## Required Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key for Claude |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `DEFAULT_AUTHOR_SLUG` | Author slug for generated posts |

## Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_MODEL` | `claude-sonnet-4-5-20250929` | Claude model to use |
| `MAX_TURNS` | `15` | Max agentic loop iterations |
| `DEFAULT_STATUS` | `draft` | Default post status (`draft`, `published`, `scheduled`) |
| `BLOGS_PER_RUN` | `1` | Number of blogs to generate per autonomous run |

## Niche & Content

| Variable | Default | Description |
|----------|---------|-------------|
| `NICHE_PROMPT_PATH` | `prompts/niche/golf.md` | Path to niche-specific prompt |
| `ALLOW_NEW_CATEGORIES` | `true` | Allow AI to create new categories |
| `DEFAULT_CATEGORY_SLUG` | - | Fallback category if none specified |

## Image Generation

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_IMAGE_GENERATION` | `false` | Enable AI image generation |
| `GEMINI_API_KEY` | - | Google AI API key (required if enabled) |
| `GEMINI_MODEL` | `gemini-2.0-flash-exp-image-generation` | Gemini model for images |
| `IMAGE_CONTEXT` | - | Site theme context (e.g., "golf course, outdoor, sunny") |
| `IMAGE_ASPECT_RATIO` | `21:9` | Image aspect ratio |
| `IMAGE_WIDTH` | `1600` | Image width in pixels |
| `IMAGE_QUALITY` | `85` | WebP quality (1-100) |
| `SUPABASE_STORAGE_BUCKET` | `blog-images` | Storage bucket name |

### Image Context Examples

The `IMAGE_CONTEXT` helps generate consistent, on-brand images:

```env
# Golf blog
IMAGE_CONTEXT=golf course, outdoor sports, sunny day, green grass

# Tech blog
IMAGE_CONTEXT=modern office, technology, clean workspace, minimal design

# Food blog
IMAGE_CONTEXT=kitchen, food photography, warm lighting, fresh ingredients

# Fitness blog
IMAGE_CONTEXT=gym, fitness equipment, active lifestyle, energetic
```

## Shopify Sync

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_SHOPIFY_SYNC` | `false` | Enable sync to Shopify |
| `SHOPIFY_STORE` | - | Store name (before .myshopify.com) |
| `SHOPIFY_CLIENT_ID` | - | OAuth Client ID from Dev Dashboard |
| `SHOPIFY_CLIENT_SECRET` | - | OAuth Client Secret |
| `SHOPIFY_API_VERSION` | `2025-01` | Shopify API version |
| `SHOPIFY_DEFAULT_AUTHOR` | - | Default author name for articles |
| `SHOPIFY_SYNC_ON_PUBLISH` | `true` | Auto-sync when posts are created |

## Example Configurations

### Minimal Setup

```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyxxxxx
DEFAULT_AUTHOR_SLUG=staff-writer
```

### With Image Generation

```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyxxxxx
DEFAULT_AUTHOR_SLUG=staff-writer

ENABLE_IMAGE_GENERATION=true
GEMINI_API_KEY=xxxxx
IMAGE_CONTEXT=modern office, technology, clean design
SUPABASE_STORAGE_BUCKET=blog-images
```

### With Shopify Sync

```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyxxxxx
DEFAULT_AUTHOR_SLUG=staff-writer

ENABLE_SHOPIFY_SYNC=true
SHOPIFY_STORE=my-store
SHOPIFY_CLIENT_ID=xxxxx
SHOPIFY_CLIENT_SECRET=xxxxx
SHOPIFY_DEFAULT_AUTHOR=Staff Writer
SHOPIFY_SYNC_ON_PUBLISH=true
```

### Production Setup

```env
# Core
ANTHROPIC_API_KEY=sk-ant-xxxxx
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyxxxxx
DEFAULT_AUTHOR_SLUG=expert-writer

# Content
CLAUDE_MODEL=claude-sonnet-4-5-20250929
MAX_TURNS=15
DEFAULT_STATUS=published
BLOGS_PER_RUN=3
NICHE_PROMPT_PATH=prompts/niche/cooking.md
ALLOW_NEW_CATEGORIES=false
DEFAULT_CATEGORY_SLUG=recipes

# Images
ENABLE_IMAGE_GENERATION=true
GEMINI_API_KEY=xxxxx
GEMINI_MODEL=gemini-2.0-flash-exp-image-generation
IMAGE_CONTEXT=kitchen, food photography, warm lighting
IMAGE_ASPECT_RATIO=16:9
IMAGE_WIDTH=1920
IMAGE_QUALITY=90
SUPABASE_STORAGE_BUCKET=blog-images

# Shopify
ENABLE_SHOPIFY_SYNC=true
SHOPIFY_STORE=my-food-blog
SHOPIFY_CLIENT_ID=xxxxx
SHOPIFY_CLIENT_SECRET=xxxxx
SHOPIFY_API_VERSION=2025-01
SHOPIFY_DEFAULT_AUTHOR=Chef Expert
SHOPIFY_SYNC_ON_PUBLISH=true
```

## Cost Estimation

Using Claude Sonnet 4.5 with prompt caching:

- ~70K tokens per blog post
- ~$0.15-0.25 per post
- 10 posts: ~$1.50-2.50

Prompt caching reduces costs by ~50% after the first turn.

## Automation

### Cron Job

```bash
# Generate 3 posts daily at 9am
0 9 * * * cd /path/to/blog-generator && python generator.py -a -c 3 >> /var/log/blog.log 2>&1
```

### GitHub Actions

Key secrets to configure:
- `ANTHROPIC_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `GEMINI_API_KEY` (if using images)
- `SHOPIFY_CLIENT_ID` (if using Shopify)
- `SHOPIFY_CLIENT_SECRET` (if using Shopify)
