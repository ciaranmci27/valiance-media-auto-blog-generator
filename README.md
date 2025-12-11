# ClutchCaddie Autonomous Blog Generator

An AI-powered blog generation system that uses Claude to create high-quality golf content for ClutchCaddie. The system connects directly to Supabase, understands your existing content structure, and creates posts with proper formatting, SEO, and tag relationships.

## Features

- **Content Block System**: Generates posts using your exact JSONB block structure (18 block types)
- **Autonomous Mode**: Process blog ideas from a queue without manual intervention
- **Context Awareness**: Reads existing categories, tags, and authors to avoid duplicates
- **SEO Optimized**: Proper titles, excerpts, and keyword metadata
- **Draft by Default**: Posts created as drafts for human review before publishing

## How It Works

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  IDEA QUEUE     │     │     CLAUDE      │     │    SUPABASE     │
│  (blog_ideas)   │ ──► │  (AI writer)    │ ──► │   (blog_posts)  │
│                 │ ◄── │                 │ ◄── │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘

Autonomous Flow:
1. Claude gets next idea from queue
2. Claims the idea (marks as in_progress)
3. Reads existing categories, tags, authors
4. Writes complete blog post with content blocks
5. Saves to Supabase as draft
6. Links relevant tags
7. Marks idea as completed
```

## Quick Start

### 1. Install Dependencies

```bash
cd blog-generator
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
DEFAULT_AUTHOR_SLUG=clutchcaddie-team
```

### 3. Set Up the Ideas Queue (One-Time)

Run the SQL in `schema/blog_ideas.sql` in your Supabase SQL editor to create the `blog_ideas` table.

### 4. Add Ideas to the Queue

```sql
INSERT INTO blog_ideas (topic, description, priority, target_category_slug) VALUES
  ('How to Fix Your Slice', 'Cover grip, swing path, and 3 drills', 90, 'instruction'),
  ('Best Putting Drills', 'Distance control and alignment', 85, 'practice');
```

### 5. Run the Generator

```bash
# Process ideas from the queue (autonomous mode)
python generator.py --autonomous

# Process multiple ideas
python generator.py --autonomous --count 5

# Or generate a specific topic (manual mode)
python generator.py "How to improve your short game"
```

## Usage Modes

### Autonomous Mode (Recommended for Automation)

Process ideas from the `blog_ideas` queue:

```bash
# Process one idea
python generator.py --autonomous

# Process up to 5 ideas
python generator.py --autonomous --count 5 --verbose

# Check queue status
python generator.py --status
```

### Manual Mode

Generate a post about a specific topic:

```bash
python generator.py "Complete guide to golf club fitting"
python generator.py "Best warm-up routine" --verbose
```

### Batch Mode

Generate from a file of topics:

```bash
python generator.py --batch topics.txt
```

`topics.txt`:
```
How to read greens like a pro
Best golf balls for high handicappers
# Comments are ignored
Mental game tips for pressure situations
```

### Interactive Mode

```bash
python generator.py --interactive
```

Commands in interactive mode:
- Type a topic to generate a post
- `status` - Show queue status
- `auto` - Process one idea from queue
- `quit` - Exit

## Content Block System

Posts are stored as JSON arrays of content blocks, not HTML. The generator creates properly structured blocks that your website renders.

### Available Block Types

| Type | Description |
|------|-------------|
| `paragraph` | Basic text (supports `<strong>`, `<em>`, `<a>`) |
| `heading` | Section titles (levels 2, 3, 4) |
| `list` | Ordered or unordered lists |
| `callout` | Tip/warning/info boxes |
| `quote` | Blockquotes with attribution |
| `table` | Data tables |
| `stats` | Statistics showcase |
| `proscons` | Pros/cons comparisons |
| `accordion` | Collapsible FAQ sections |
| `checklist` | Interactive checklists |
| `image` | Images with captions |
| `gallery` | Image grids |
| `video` | YouTube/Vimeo embeds |
| `button` | Call-to-action buttons |
| `tableOfContents` | Auto-generated TOC |
| `divider` | Section separators |
| `code` | Code snippets |
| `embed` | Social media embeds |

### Example Content Block

```json
{
  "id": "tip-1",
  "type": "callout",
  "data": {
    "style": "tip",
    "title": "Pro Tip",
    "text": "Check your grip first - it's the fastest fix for a slice."
  }
}
```

## Blog Ideas Queue

The `blog_ideas` table stores topics for autonomous generation.

### Schema

| Column | Description |
|--------|-------------|
| `id` | UUID primary key |
| `topic` | The main topic (required) |
| `description` | Detailed guidance for the AI |
| `notes` | Additional notes |
| `priority` | 0-100, higher = processed first |
| `target_category_slug` | Suggested category |
| `suggested_tags` | Array of suggested tag slugs |
| `status` | pending, in_progress, completed, failed, skipped |
| `blog_post_id` | Link to created post (when completed) |

### Managing the Queue

```sql
-- Add an idea
INSERT INTO blog_ideas (topic, description, priority)
VALUES ('My Topic', 'Description here', 80);

-- View pending ideas
SELECT topic, priority FROM blog_ideas
WHERE status = 'pending'
ORDER BY priority DESC;

-- View completed ideas with their posts
SELECT bi.topic, bp.title, bp.slug
FROM blog_ideas bi
JOIN blog_posts bp ON bi.blog_post_id = bp.id
WHERE bi.status = 'completed';

-- Retry a failed idea
UPDATE blog_ideas
SET status = 'pending', error_message = NULL
WHERE id = 'uuid-here';
```

## Project Structure

```
blog-generator/
├── generator.py              # Main entry point
├── config.py                 # Configuration
├── requirements.txt          # Dependencies
├── .env.example              # Environment template
├── tools/
│   ├── __init__.py
│   ├── query_tools.py        # Read from Supabase
│   ├── write_tools.py        # Write to Supabase
│   └── idea_tools.py         # Queue management
├── prompts/
│   └── system_prompt.md      # Claude instructions
├── schema/
│   └── blog_ideas.sql        # Queue table schema
└── README.md
```

## Automation

### Cron Job

```bash
# Run every day at 9am, process 3 ideas
0 9 * * * cd /path/to/blog-generator && python generator.py --autonomous --count 3 >> /var/log/blog-gen.log 2>&1
```

### GitHub Actions

```yaml
name: Generate Blog Posts

on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9am UTC
  workflow_dispatch:

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r blog-generator/requirements.txt

      - name: Process blog queue
        working-directory: blog-generator
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
          DEFAULT_AUTHOR_SLUG: clutchcaddie-team
        run: python generator.py --autonomous --count 3 --verbose
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Anthropic API key |
| `SUPABASE_URL` | Yes | - | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | - | Supabase service role key |
| `DEFAULT_AUTHOR_SLUG` | Yes | - | Author for AI posts |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-20250514` | Model to use |
| `MAX_TURNS` | No | `15` | Max tool iterations |
| `DEFAULT_STATUS` | No | `draft` | Post status |

## Troubleshooting

### "anthropic package not installed"
```bash
pip install anthropic
```

### "Missing required environment variables"
Ensure `.env` exists with all required values.

### Posts not appearing on website
Posts are created as `draft`. Change status to `published` in Supabase.

### Queue status shows "in_progress" stuck
An idea may be stuck if the generator crashed. Reset it:
```sql
UPDATE blog_ideas SET status = 'pending' WHERE status = 'in_progress';
```

## Cost Estimation

Using Claude Sonnet (recommended):
- ~20-50K tokens per blog post
- ~$0.06-0.15 per post
- 10 posts: ~$0.60-1.50

## License

Internal tool for ClutchCaddie.
