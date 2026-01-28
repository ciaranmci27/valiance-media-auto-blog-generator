# Shopify Theme CSS for Blog Content Blocks

This document explains how to add styles for blog content blocks synced from Supabase.

## How It Works

The CSS is designed to **inherit your Shopify theme's styling** wherever possible:

- **Text colors** - Inherited from your theme (paragraphs, headings, lists, tables, etc.)
- **Backgrounds** - Only set on elements that need them (callouts, code blocks, pros/cons)
- **Borders** - Use semi-transparent colors that adapt to light/dark themes

This means your synced blog content will automatically match your theme's look and feel.

## Adding the CSS

### Option 1: Upload as Asset (Recommended)

1. Go to Shopify Admin → Online Store → Themes
2. Click "Edit code" on your active theme
3. In the `assets/` folder, click "Add a new asset"
4. Upload [blog-styles.css](blog-styles.css)
5. Include it in your theme by adding this to `layout/theme.liquid` in the `<head>`:

```liquid
{{ 'blog-styles.css' | asset_url | stylesheet_tag }}
```

### Option 2: Copy into Theme CSS

1. Go to Shopify Admin → Online Store → Themes
2. Click "Edit code" on your active theme
3. Find `assets/base.css` or `assets/theme.css`
4. Copy the contents of [blog-styles.css](blog-styles.css) to the end of the file
5. Save

## Customizing

### Accent Color

The default accent color is emerald green (`#059669`). To match your brand, search and replace these values in the CSS:

| Color | Usage |
|-------|-------|
| `#059669` | Primary accent (links, buttons) |
| `#047857` | Accent hover state |
| `#10b981` | Success/positive elements |
| `#d1fae5` | Light accent backgrounds |

### Callout Colors

Each callout type has its own color scheme. The CSS defines both background AND text colors together to ensure readability:

- **Tip/Success**: Green background with dark green text
- **Info**: Blue background with dark blue text
- **Warning**: Amber background with dark amber text
- **Error**: Red background with dark red text
- **Note**: Neutral (inherits from theme)

## Content Block Types

The CSS supports all 18 content block types:

| Block Type | Class Prefix |
|------------|--------------|
| Paragraph | `.blog-paragraph` |
| Heading | `.blog-heading` |
| Quote | `.quote` |
| List | `.list` |
| Checklist | `.checklist` |
| Pros & Cons | `.pros-cons` |
| Image | `.image` |
| Gallery | `.gallery` |
| Video Embed | `.video-embed` |
| Social Embed | `.embed` |
| Table | `.table` |
| Stats | `.stats` |
| Accordion | `.accordion` |
| Button | `.button` |
| Table of Contents | `.toc` |
| Code Block | `.code-block` |
| Callout | `.callout` |
| Divider | `.divider` |
