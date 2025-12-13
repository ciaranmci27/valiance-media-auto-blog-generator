# Shopify SEO Theme Setup

This guide explains how to configure your Shopify theme to properly use SEO meta descriptions for blogs and articles synced from Supabase.

## The Problem

Shopify's GraphQL API does not support setting SEO meta descriptions for Blogs or Articles programmatically. The `seo` field that exists for Products and Collections is **not available** for blog content.

| Resource | SEO via API | Solution |
|----------|-------------|----------|
| Products | Yes | N/A |
| Collections | Yes | N/A |
| **Blogs** | **No** | Metafields + Theme |
| **Articles** | **No** | Use `summary` in Theme |

## The Solution

We sync the article excerpt to Shopify's `summary` field. Your theme just needs to use this as the meta description.

---

## Quick Fix: Update theme.liquid

The fastest fix is to update your `layout/theme.liquid` file. This is where the `<head>` section lives and where meta tags are rendered.

### Step 1: Open layout/theme.liquid

In your Shopify theme editor, open `layout/theme.liquid`.

### Step 2: Find the Existing Meta Description

Search for `<meta name="description"`. You'll find something like one of these:

```liquid
{%- comment -%} Common pattern 1 {%- endcomment -%}
<meta name="description" content="{{ page_description | escape }}">

{%- comment -%} Common pattern 2 {%- endcomment -%}
{%- if page_description -%}
  <meta name="description" content="{{ page_description | escape }}">
{%- endif -%}

{%- comment -%} Common pattern 3 {%- endcomment -%}
<meta name="description" content="{{ page_description | default: shop.description | escape }}">
```

### Step 3: Replace With This

Replace the existing meta description tag with this code:

```liquid
{%- comment -%} SEO Meta Description - Articles use excerpt, everything else uses page_description {%- endcomment -%}
{%- if template.name == 'article' and article.excerpt != blank -%}
  <meta name="description" content="{{ article.excerpt | strip_html | strip_newlines | truncate: 160 | escape }}">
{%- elsif template.name == 'blog' and blog.metafields.seo.description != blank -%}
  <meta name="description" content="{{ blog.metafields.seo.description | strip_html | strip_newlines | truncate: 160 | escape }}">
{%- elsif page_description != blank -%}
  <meta name="description" content="{{ page_description | escape }}">
{%- elsif shop.description != blank -%}
  <meta name="description" content="{{ shop.description | escape }}">
{%- endif -%}
```

This handles:
- **Article pages**: Uses the excerpt (synced from Supabase)
- **Blog pages**: Uses metafield if available
- **Other pages**: Uses the default page_description
- **Fallback**: Uses shop description

### Step 4: Save and Test

1. Save the file
2. Visit an article page
3. Right-click > View Page Source
4. Search for `<meta name="description"` - you should see your excerpt

---

## Understanding Your Theme Structure

Different themes organize SEO differently. Here's where to look:

| File | What's There | When to Edit |
|------|--------------|--------------|
| `layout/theme.liquid` | Main `<head>` section with meta tags | **Usually here** - edit the meta description tag |
| `snippets/head-tag.liquid` | Some themes extract head content here | Check if your theme uses this |
| `sections/main-article.liquid` | Article page content | JSON-LD structured data is often here |
| `templates/article.liquid` | Article template (older themes) | Rarely has meta tags |

### What to Look For

1. **Meta description tag**: `<meta name="description"`
2. **Open Graph description**: `<meta property="og:description"`
3. **Twitter description**: `<meta name="twitter:description"`
4. **JSON-LD structured data**: `<script type="application/ld+json">` with `"description":`

Your **JSON-LD** (structured data) may already have the excerpt - that's separate from the meta tag and both should exist.

---

## Blog SEO (Category Pages)

Blogs (categories) don't have a summary field like articles. We use metafields to store SEO data.

### How It Works

When you sync categories with `--shopify-sync-categories`, the system automatically creates SEO metafields in Shopify **if** your Supabase `blog_categories` table has SEO data populated.

**Required**: Your category must have the `seo` JSON field populated in Supabase:
```json
{
  "title": "Your SEO Title",
  "description": "Your meta description for this category",
  "keywords": "keyword1, keyword2, keyword3"
}
```

The sync creates these Shopify metafields:
- `seo.title` - SEO title override
- `seo.description` - Meta description
- `seo.keywords` - Keywords (comma-separated)

### Theme Configuration

Add this to `sections/main-blog.liquid` or `templates/blog.liquid`:

```liquid
{%- comment -%}
  Blog SEO Meta Description
  Uses metafield if available, otherwise generates from first article
{%- endcomment -%}

{%- liquid
  if blog.metafields.seo.description != blank
    assign blog_meta_description = blog.metafields.seo.description | strip_html | strip_newlines | truncate: 160
  elsif blog.articles.first.excerpt != blank
    assign blog_meta_description = blog.articles.first.excerpt | strip_html | strip_newlines | truncate: 160
  endif
-%}

{%- if blog_meta_description != blank -%}
  <meta name="description" content="{{ blog_meta_description | escape }}">
  <meta property="og:description" content="{{ blog_meta_description | escape }}">
  <meta name="twitter:description" content="{{ blog_meta_description | escape }}">
{%- endif -%}
```

### Alternative: Manual Entry in Shopify

If you don't have SEO data in Supabase, you can set the meta description manually in Shopify Admin:
1. Go to **Online Store** > **Blog posts** > **Manage blogs**
2. Click on the blog (category)
3. Scroll to **Search engine listing**
4. Enter your meta description

---

## Verification

After making changes:

1. **View Page Source**: Visit an article page, right-click, "View Page Source", search for `<meta name="description"`
2. **Google Rich Results Test**: Use [Google's Rich Results Test](https://search.google.com/test/rich-results) to verify your meta tags
3. **SEO Browser Extensions**: Tools like "SEO META in 1 CLICK" can show your meta tags

---

## Complete Example: article-seo.liquid Snippet

Create `snippets/article-seo.liquid`:

```liquid
{%- comment -%}
  Article SEO Snippet
  Include this in your article template with: {% render 'article-seo', article: article %}

  This outputs:
  - Meta description (from summary/excerpt)
  - Open Graph tags
  - Twitter Card tags
  - JSON-LD structured data
{%- endcomment -%}

{%- liquid
  # Get meta description from summary or content
  if article.excerpt != blank
    assign seo_description = article.excerpt | strip_html | strip_newlines | truncate: 160
  elsif article.content != blank
    assign seo_description = article.content | strip_html | strip_newlines | truncate: 160
  else
    assign seo_description = shop.description | truncate: 160
  endif

  # Get featured image
  if article.image
    assign seo_image = article.image | image_url: width: 1200
  endif
-%}

{%- comment -%} Basic Meta {%- endcomment -%}
<meta name="description" content="{{ seo_description | escape }}">

{%- comment -%} Open Graph {%- endcomment -%}
<meta property="og:title" content="{{ article.title | escape }}">
<meta property="og:description" content="{{ seo_description | escape }}">
<meta property="og:type" content="article">
<meta property="og:url" content="{{ canonical_url }}">
{%- if seo_image -%}
  <meta property="og:image" content="{{ seo_image }}">
{%- endif -%}
<meta property="article:published_time" content="{{ article.published_at | date: '%Y-%m-%dT%H:%M:%S%z' }}">
<meta property="article:author" content="{{ article.author }}">
{%- for tag in article.tags -%}
  <meta property="article:tag" content="{{ tag }}">
{%- endfor -%}

{%- comment -%} Twitter Card {%- endcomment -%}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{{ article.title | escape }}">
<meta name="twitter:description" content="{{ seo_description | escape }}">
{%- if seo_image -%}
  <meta name="twitter:image" content="{{ seo_image }}">
{%- endif -%}

{%- comment -%} JSON-LD Structured Data {%- endcomment -%}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": {{ article.title | json }},
  "description": {{ seo_description | json }},
  "datePublished": "{{ article.published_at | date: '%Y-%m-%dT%H:%M:%S%z' }}",
  "dateModified": "{{ article.updated_at | date: '%Y-%m-%dT%H:%M:%S%z' }}",
  "author": {
    "@type": "Person",
    "name": {{ article.author | json }}
  },
  "publisher": {
    "@type": "Organization",
    "name": {{ shop.name | json }},
    "logo": {
      "@type": "ImageObject",
      "url": "{{ shop.brand.logo | image_url: width: 600 }}"
    }
  }
  {%- if seo_image -%}
  ,"image": "{{ seo_image }}"
  {%- endif -%}
  {%- if article.tags.size > 0 -%}
  ,"keywords": {{ article.tags | join: ', ' | json }}
  {%- endif -%}
}
</script>
```

---

## Complete Example: blog-seo.liquid Snippet

Create `snippets/blog-seo.liquid`:

```liquid
{%- comment -%}
  Blog SEO Snippet
  Include this in your blog template with: {% render 'blog-seo', blog: blog %}
{%- endcomment -%}

{%- liquid
  # Get meta description from metafield or first article
  if blog.metafields.seo.description != blank
    assign seo_description = blog.metafields.seo.description | strip_html | strip_newlines | truncate: 160
  elsif blog.articles.first.excerpt != blank
    assign seo_description = blog.articles.first.excerpt | strip_html | strip_newlines | truncate: 160
  else
    assign seo_description = shop.description | truncate: 160
  endif

  # Get image from first article if available
  if blog.articles.first.image
    assign seo_image = blog.articles.first.image | image_url: width: 1200
  endif
-%}

{%- comment -%} Basic Meta {%- endcomment -%}
<meta name="description" content="{{ seo_description | escape }}">

{%- comment -%} Open Graph {%- endcomment -%}
<meta property="og:title" content="{{ blog.title | escape }}">
<meta property="og:description" content="{{ seo_description | escape }}">
<meta property="og:type" content="website">
<meta property="og:url" content="{{ canonical_url }}">
{%- if seo_image -%}
  <meta property="og:image" content="{{ seo_image }}">
{%- endif -%}

{%- comment -%} Twitter Card {%- endcomment -%}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{{ blog.title | escape }}">
<meta name="twitter:description" content="{{ seo_description | escape }}">
{%- if seo_image -%}
  <meta name="twitter:image" content="{{ seo_image }}">
{%- endif -%}

{%- comment -%} JSON-LD Structured Data {%- endcomment -%}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Blog",
  "name": {{ blog.title | json }},
  "description": {{ seo_description | json }},
  "url": "{{ shop.url }}{{ blog.url }}",
  "publisher": {
    "@type": "Organization",
    "name": {{ shop.name | json }}
  }
}
</script>
```

---

## Troubleshooting

### Meta description not showing

1. Check your theme's `layout/theme.liquid` for an existing `<meta name="description">` that might override yours
2. Make sure the article has an excerpt/summary (check in Shopify admin)
3. Clear your browser cache and Shopify's cache

### Duplicate meta descriptions

Search your theme for all instances of `<meta name="description"` and consolidate them into one conditional block.

### Summary/excerpt is empty

Ensure your Supabase posts have the `excerpt` field populated. The sync maps `excerpt` to Shopify's `summary` field.
