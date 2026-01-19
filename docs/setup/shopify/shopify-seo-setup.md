# Shopify SEO Setup

Complete guide to configuring SEO for blog content synced from Supabase.

## Overview

Shopify's API doesn't support setting SEO meta descriptions for Blogs or Articles directly. This guide shows you how to configure your theme to use the synced content (excerpts, metafields) for proper SEO.

| Content Type | SEO Source | What We Do |
|--------------|------------|------------|
| Articles | `excerpt` field | Use article excerpt as meta description |
| Blogs (categories) | `seo` metafields | Sync SEO data from Supabase to Shopify metafields |

---

## Quick Setup (3 Steps)

### Step 1: Create Article SEO Snippet

1. In Shopify Admin, go to **Online Store → Themes → Edit code**
2. In the **Snippets** folder, click **Add a new snippet**
3. Name it `article-seo`
4. Paste this code:

```liquid
{%- comment -%}
  Article SEO Snippet
  Provides: meta description, Open Graph, Twitter Cards, JSON-LD schema
{%- endcomment -%}

{%- liquid
  if article.excerpt != blank
    assign seo_description = article.excerpt | strip_html | strip_newlines | truncate: 160
  elsif article.content != blank
    assign seo_description = article.content | strip_html | strip_newlines | truncate: 160
  else
    assign seo_description = shop.description | truncate: 160
  endif

  if article.image
    assign seo_image = article.image | image_url: width: 1200
  endif
-%}

<meta name="description" content="{{ seo_description | escape }}">

<meta property="og:site_name" content="{{ shop.name }}">
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

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{{ article.title | escape }}">
<meta name="twitter:description" content="{{ seo_description | escape }}">
{%- if seo_image -%}
  <meta name="twitter:image" content="{{ seo_image }}">
{%- endif -%}

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
    "name": {{ shop.name | json }}
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

5. Click **Save**

---

### Step 2: Create Blog SEO Snippet

1. In the **Snippets** folder, click **Add a new snippet**
2. Name it `blog-seo`
3. Paste this code:

```liquid
{%- comment -%}
  Blog (Category) SEO Snippet
  Provides: meta description, Open Graph, Twitter Cards, JSON-LD schema
  Uses metafields synced from Supabase blog_categories.seo field
{%- endcomment -%}

{%- liquid
  if blog.metafields.seo.description != blank
    assign seo_description = blog.metafields.seo.description | strip_html | strip_newlines | truncate: 160
  elsif blog.articles.first.excerpt != blank
    assign seo_description = blog.articles.first.excerpt | strip_html | strip_newlines | truncate: 160
  else
    assign seo_description = shop.description | truncate: 160
  endif

  if blog.articles.first.image
    assign seo_image = blog.articles.first.image | image_url: width: 1200
  endif
-%}

<meta name="description" content="{{ seo_description | escape }}">

<meta property="og:site_name" content="{{ shop.name }}">
<meta property="og:title" content="{{ blog.title | escape }}">
<meta property="og:description" content="{{ seo_description | escape }}">
<meta property="og:type" content="website">
<meta property="og:url" content="{{ canonical_url }}">
{%- if seo_image -%}
  <meta property="og:image" content="{{ seo_image }}">
{%- endif -%}

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{{ blog.title | escape }}">
<meta name="twitter:description" content="{{ seo_description | escape }}">
{%- if seo_image -%}
  <meta name="twitter:image" content="{{ seo_image }}">
{%- endif -%}

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

4. Click **Save**

---

### Step 3: Update meta-tags.liquid

1. In the **Snippets** folder, open `meta-tags.liquid`
2. Find the meta description section at the bottom (usually looks like):

```liquid
{% if page_description %}
  <meta
    name="description"
    content="{{ page_description | escape }}"
  >
{% endif %}
```

3. Replace the **entire file** with this updated version:

```liquid
<meta charset="utf-8">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="view-transition" content="same-origin">
<meta name="theme-color" content="">

{%- liquid
  assign og_title = page_title | default: shop.name
  assign og_url = canonical_url | default: request.origin
  assign og_type = 'website'
  assign og_description = page_description | default: shop.description | default: shop.name

  if request.page_type == 'product'
    assign og_type = 'product'
  elsif request.page_type == 'article'
    assign og_type = 'article'
  elsif request.page_type == 'password'
    assign og_url = request.origin
  endif
%}

<title>
  {{ page_title }}
  {%- if current_tags %} &ndash; tagged "{{ current_tags | join: ', ' }}"{% endif -%}
  {%- if current_page != 1 %} &ndash; Page {{ current_page }}{% endif -%}
  {%- unless page_title contains shop.name %} &ndash; {{ shop.name }}{% endunless -%}
</title>

<link rel="canonical" href="{{ canonical_url }}">

{%- comment -%}
  SEO Meta Tags
  - Articles: Use article-seo snippet (excerpt + structured data)
  - Blogs: Use blog-seo snippet (metafields + structured data)
  - Other pages: Default Shopify behavior
{%- endcomment -%}

{%- if template.name == 'article' -%}
  {% render 'article-seo', article: article %}
{%- elsif template.name == 'blog' -%}
  {% render 'blog-seo', blog: blog %}
{%- else -%}
  {%- comment -%} Default meta tags for products, collections, pages, etc. {%- endcomment -%}
  <meta property="og:site_name" content="{{ shop.name }}">
  <meta property="og:url" content="{{ og_url }}">
  <meta property="og:title" content="{{ og_title | escape }}">
  <meta property="og:type" content="{{ og_type }}">
  <meta property="og:description" content="{{ og_description | escape }}">

  {%- if page_image -%}
    <meta property="og:image" content="http:{{ page_image | image_url }}">
    <meta property="og:image:secure_url" content="https:{{ page_image | image_url }}">
    <meta property="og:image:width" content="{{ page_image.width }}">
    <meta property="og:image:height" content="{{ page_image.height }}">
  {%- endif -%}

  {%- if request.page_type == 'product' -%}
    <meta property="og:price:amount" content="{{ product.price | money_without_currency | strip_html }}">
    <meta property="og:price:currency" content="{{ cart.currency.iso_code }}">
  {%- endif -%}

  {%- if settings.social_twitter_link != blank -%}
    <meta name="twitter:site" content="{{ settings.social_twitter_link | split: 'twitter.com/' | last | prepend: '@' }}">
  {%- endif -%}
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{{ og_title | escape }}">
  <meta name="twitter:description" content="{{ og_description | escape }}">

  {% if page_description %}
    <meta name="description" content="{{ page_description | escape }}">
  {% endif %}
{%- endif -%}
```

4. Click **Save**

---

## Category SEO Setup (Supabase)

For blog/category pages to have custom SEO, you need to populate the `seo` JSONB field in your `blog_categories` table.

### SEO Field Structure

```json
{
  "title": "Your SEO Title | Brand Name",
  "description": "Your meta description for this category (max 160 chars)",
  "keywords": "keyword1, keyword2, keyword3"
}
```

### Example SQL

```sql
UPDATE blog_categories
SET seo = '{
  "title": "Natural Remedies & Holistic Healing | Your Brand",
  "description": "Discover natural remedies and holistic healing solutions. Learn about tallow moisturizers, CBD salves, and chemical-free skincare.",
  "keywords": "natural remedies, holistic healing, tallow moisturizer"
}'::jsonb
WHERE slug = 'natural-remedies';
```

### Sync to Shopify

After updating SEO in Supabase, sync to push the metafields:

```bash
python generator.py --shopify-sync-categories --force
```

This creates these Shopify metafields on each blog:
- `seo.title`
- `seo.description`
- `seo.keywords`

---

## Verification

### Check Article SEO

1. Visit any article page on your store
2. Right-click → **View Page Source**
3. Search for `<meta name="description"` - should show your excerpt
4. Search for `"BlogPosting"` - should show JSON-LD structured data

### Check Blog SEO

1. Visit a blog/category page (e.g., `/blogs/news`)
2. Right-click → **View Page Source**
3. Search for `<meta name="description"` - should show your SEO description
4. Search for `"Blog"` in the JSON-LD section

### Tools

- [Google Rich Results Test](https://search.google.com/test/rich-results) - Verify structured data
- [Facebook Sharing Debugger](https://developers.facebook.com/tools/debug/) - Test Open Graph tags
- Browser extensions like "SEO META in 1 CLICK"

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    meta-tags.liquid                          │
│                                                              │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐   │
│  │  Article?   │   │   Blog?     │   │  Other pages    │   │
│  │             │   │             │   │                 │   │
│  │  Render     │   │  Render     │   │  Default        │   │
│  │  article-   │   │  blog-      │   │  Shopify        │   │
│  │  seo.liquid │   │  seo.liquid │   │  meta tags      │   │
│  └─────────────┘   └─────────────┘   └─────────────────┘   │
└─────────────────────────────────────────────────────────────┘

Article SEO Sources:
  - Meta description → article.excerpt (synced from Supabase)
  - Open Graph → article title, excerpt, image
  - JSON-LD → BlogPosting schema

Blog SEO Sources:
  - Meta description → blog.metafields.seo.description (synced from Supabase)
  - Fallback → first article's excerpt
  - JSON-LD → Blog schema
```

---

## File Reference

| File | Purpose |
|------|---------|
| `snippets/article-seo.liquid` | SEO tags for article pages |
| `snippets/blog-seo.liquid` | SEO tags for blog/category pages |
| `snippets/meta-tags.liquid` | Routes to correct SEO snippet |
| `layout/theme.liquid` | Includes meta-tags (no changes needed) |

---

## Troubleshooting

### Meta description not showing

1. Check that the article has an excerpt in Supabase
2. Verify the sync completed: `python generator.py --shopify-status`
3. Clear browser cache and try again

### Blog SEO not showing

1. Check that `blog_categories.seo` is populated in Supabase
2. Re-sync categories: `python generator.py --shopify-sync-categories --force`
3. Verify metafields exist in Shopify Admin under the blog settings

### Duplicate meta descriptions

Search your theme for all instances of `<meta name="description"` and ensure only the meta-tags.liquid version remains.

### JSON-LD not appearing

Check for JavaScript errors in browser console. The JSON-LD script may have a syntax error if special characters aren't properly escaped.

---

## Next Steps

- [Shopify Theme CSS](shopify-theme-css.md) - Style the content blocks
- [Getting Started with Shopify](getting-started-with-shopify.md) - Full setup guide
