# Content Block System

Posts are stored as JSON arrays of content blocks, not HTML. Your frontend must render these blocks.

## Example Post Structure

```json
{
  "title": "How to Get Started",
  "slug": "how-to-get-started",
  "excerpt": "A beginner's guide...",
  "content": [
    {
      "id": "intro-1",
      "type": "paragraph",
      "data": {
        "text": "Welcome to this guide..."
      }
    },
    {
      "id": "heading-1",
      "type": "heading",
      "data": {
        "level": 2,
        "text": "Getting Started"
      }
    },
    {
      "id": "tip-1",
      "type": "callout",
      "data": {
        "style": "tip",
        "title": "Pro Tip",
        "text": "Start with the basics."
      }
    }
  ]
}
```

## Default Block Types

The included system prompt defines these block types (customize as needed):

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

## Adapting Block Types

To use different block types:

1. Edit `prompts/system_prompt.md` to define your block schemas
2. Build corresponding React/Vue/etc. components to render each type
3. The AI will generate content using whatever block types you define

### Example: Simplified Blocks

If you only need paragraphs, headings, and lists, simplify the system prompt:

```markdown
## Content Blocks

Generate content using these block types only:

### paragraph
{ "id": "string", "type": "paragraph", "data": { "text": "string" } }

### heading
{ "id": "string", "type": "heading", "data": { "level": 2|3|4, "text": "string" } }

### list
{ "id": "string", "type": "list", "data": { "style": "ordered|unordered", "items": ["string"] } }
```

## Block Type Reference

### paragraph

Basic text content with optional inline formatting.

```json
{
  "id": "p-1",
  "type": "paragraph",
  "data": {
    "text": "This is a paragraph with <strong>bold</strong> and <em>italic</em> text."
  }
}
```

### heading

Section headers (levels 2-4, never use level 1).

```json
{
  "id": "h-1",
  "type": "heading",
  "data": {
    "level": 2,
    "text": "Section Title"
  }
}
```

### list

Ordered or unordered lists.

```json
{
  "id": "list-1",
  "type": "list",
  "data": {
    "style": "unordered",
    "items": ["First item", "Second item", "Third item"]
  }
}
```

### callout

Highlighted boxes for tips, warnings, or important info.

```json
{
  "id": "callout-1",
  "type": "callout",
  "data": {
    "style": "tip",
    "title": "Pro Tip",
    "text": "This is helpful advice."
  }
}
```

Styles: `tip`, `warning`, `info`, `success`

### quote

Blockquotes with optional attribution.

```json
{
  "id": "quote-1",
  "type": "quote",
  "data": {
    "text": "The quote text here.",
    "attribution": "Author Name"
  }
}
```

### table

Data tables with headers and rows.

```json
{
  "id": "table-1",
  "type": "table",
  "data": {
    "headers": ["Column 1", "Column 2", "Column 3"],
    "rows": [
      ["Row 1 Col 1", "Row 1 Col 2", "Row 1 Col 3"],
      ["Row 2 Col 1", "Row 2 Col 2", "Row 2 Col 3"]
    ]
  }
}
```

### stats

Statistics display with label/value pairs.

```json
{
  "id": "stats-1",
  "type": "stats",
  "data": {
    "items": [
      {"label": "Users", "value": "10,000+"},
      {"label": "Countries", "value": "50"},
      {"label": "Uptime", "value": "99.9%"}
    ]
  }
}
```

### proscons

Pros and cons comparison lists.

```json
{
  "id": "proscons-1",
  "type": "proscons",
  "data": {
    "pros": ["Benefit one", "Benefit two"],
    "cons": ["Drawback one", "Drawback two"]
  }
}
```

### accordion

Collapsible FAQ sections.

```json
{
  "id": "faq-1",
  "type": "accordion",
  "data": {
    "items": [
      {"question": "First question?", "answer": "First answer."},
      {"question": "Second question?", "answer": "Second answer."}
    ]
  }
}
```

### image

Single image with caption.

```json
{
  "id": "img-1",
  "type": "image",
  "data": {
    "src": "https://example.com/image.jpg",
    "alt": "Description of image",
    "caption": "Optional caption text"
  }
}
```

### video

YouTube or Vimeo embeds.

```json
{
  "id": "video-1",
  "type": "video",
  "data": {
    "platform": "youtube",
    "videoId": "dQw4w9WgXcQ",
    "title": "Video title"
  }
}
```

### button

Call-to-action buttons.

```json
{
  "id": "btn-1",
  "type": "button",
  "data": {
    "text": "Learn More",
    "url": "https://example.com",
    "style": "primary"
  }
}
```

Styles: `primary`, `secondary`, `outline`
