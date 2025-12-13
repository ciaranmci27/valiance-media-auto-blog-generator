# Shopify Theme CSS for Blog Content Blocks

This document contains the CSS needed to style blog content blocks synced from Supabase. Add this CSS to your Shopify theme's stylesheet to ensure synced articles display correctly.

## Adding the CSS

1. Go to Shopify Admin → Online Store → Themes
2. Click "Edit code" on your active theme
3. Find `assets/base.css` or `assets/theme.css`
4. Add the CSS below at the end of the file
5. Save

## Content Block Styles

```css
/* =============================================================================
   Blog Content Block Styles
   Add this CSS to your Shopify theme for synced blog content
   ============================================================================= */

/* -----------------------------------------------------------------------------
   TYPOGRAPHY - Paragraphs & Headings
   ----------------------------------------------------------------------------- */

.blog-paragraph {
  margin-bottom: 1.5rem;
  line-height: 1.75;
  color: #374151;
  font-size: 1.125rem;
}

.blog-paragraph a {
  color: #059669;
  text-decoration: underline;
}

.blog-paragraph a:hover {
  color: #047857;
}

.blog-paragraph strong {
  font-weight: 600;
  color: #111827;
}

.blog-heading {
  font-weight: 700;
  color: #111827;
  line-height: 1.25;
}

.blog-heading--h2 {
  font-size: 1.875rem;
  margin-top: 3rem;
  margin-bottom: 1.5rem;
}

.blog-heading--h3 {
  font-size: 1.5rem;
  margin-top: 2.5rem;
  margin-bottom: 1rem;
}

.blog-heading--h4 {
  font-size: 1.25rem;
  margin-top: 2rem;
  margin-bottom: 0.75rem;
}

/* Scroll margin for anchor links */
.blog-heading[id] {
  scroll-margin-top: 6rem;
}

/* -----------------------------------------------------------------------------
   QUOTES
   ----------------------------------------------------------------------------- */

.quote {
  margin: 2rem 0;
  padding: 1.5rem 2rem;
  border-left: 4px solid #10b981;
  background: linear-gradient(to right, #f9fafb, transparent);
  border-radius: 0 0.75rem 0.75rem 0;
}

.quote__text {
  font-style: italic;
  font-size: 1.25rem;
  line-height: 1.625;
  color: #374151;
  margin: 0;
}

.quote__footer {
  margin-top: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.quote__footer::before {
  content: "";
  display: block;
  width: 40px;
  height: 1px;
  background: #d1d5db;
}

.quote__attribution {
  font-weight: 600;
  color: #111827;
  font-style: normal;
}

.quote__role {
  color: #6b7280;
  font-size: 0.875rem;
  font-style: normal;
}

/* -----------------------------------------------------------------------------
   LISTS
   ----------------------------------------------------------------------------- */

.list {
  margin-bottom: 1.5rem;
  list-style: none;
  padding: 0;
}

.list__item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  color: #374151;
}

.list__bullet {
  flex-shrink: 0;
  width: 0.5rem;
  height: 0.5rem;
  margin-top: 0.625rem;
  border-radius: 50%;
  background: #10b981;
}

.list__number {
  flex-shrink: 0;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 50%;
  background: #d1fae5;
  color: #047857;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  font-weight: 600;
}

.list__content a {
  color: #059669;
  text-decoration: underline;
}

.list__content strong {
  font-weight: 600;
  color: #111827;
}

/* -----------------------------------------------------------------------------
   CHECKLIST
   ----------------------------------------------------------------------------- */

.checklist {
  margin: 1.5rem 0;
  padding: 1.5rem;
  background: #f9fafb;
  border-radius: 0.75rem;
  border: 1px solid #e5e7eb;
}

.checklist__title {
  font-weight: 600;
  color: #111827;
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.checklist__list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.checklist__item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.checklist__check {
  flex-shrink: 0;
  width: 1.25rem;
  height: 1.25rem;
  margin-top: 0.125rem;
  border-radius: 0.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
}

.checklist__item--checked .checklist__check {
  background: #10b981;
  color: white;
}

.checklist__check--empty {
  border: 2px solid #d1d5db;
}

.checklist__item--checked .checklist__text {
  text-decoration: line-through;
  opacity: 0.6;
}

/* -----------------------------------------------------------------------------
   PROS & CONS
   ----------------------------------------------------------------------------- */

.pros-cons {
  margin: 2rem 0;
}

.pros-cons__title {
  font-weight: 600;
  font-size: 1.25rem;
  color: #111827;
  margin-bottom: 1rem;
}

.pros-cons__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 768px) {
  .pros-cons__grid {
    grid-template-columns: 1fr;
  }
}

.pros-cons__section {
  padding: 1.25rem;
  border-radius: 0.75rem;
}

.pros-cons__section--pros {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
}

.pros-cons__section--cons {
  background: #fef2f2;
  border: 1px solid #fecaca;
}

.pros-cons__heading {
  font-weight: 600;
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.pros-cons__heading--pros {
  color: #065f46;
}

.pros-cons__heading--cons {
  color: #991b1b;
}

.pros-cons__badge {
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  color: white;
}

.pros-cons__heading--pros .pros-cons__badge {
  background: #10b981;
}

.pros-cons__heading--cons .pros-cons__badge {
  background: #ef4444;
}

.pros-cons__list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.pros-cons__item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.pros-cons__item--pro {
  color: #065f46;
}

.pros-cons__item--con {
  color: #991b1b;
}

.pros-cons__icon {
  font-weight: bold;
}

/* -----------------------------------------------------------------------------
   IMAGES & GALLERY
   ----------------------------------------------------------------------------- */

.image {
  margin: 2rem 0;
}

.image--small {
  max-width: 24rem;
  margin-left: auto;
  margin-right: auto;
}

.image--medium {
  max-width: 36rem;
  margin-left: auto;
  margin-right: auto;
}

.image--large {
  max-width: 48rem;
  margin-left: auto;
  margin-right: auto;
}

.image--full {
  width: 100%;
}

.image__img {
  width: 100%;
  height: auto;
  border-radius: 0.75rem;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
}

.image__caption {
  margin-top: 0.75rem;
  text-align: center;
  font-size: 0.875rem;
  color: #6b7280;
}

.gallery {
  margin: 2rem 0;
  display: grid;
  gap: 1rem;
}

.gallery--columns-2 {
  grid-template-columns: repeat(2, 1fr);
}

.gallery--columns-3 {
  grid-template-columns: repeat(2, 1fr);
}

.gallery--columns-4 {
  grid-template-columns: repeat(2, 1fr);
}

@media (min-width: 768px) {
  .gallery--columns-3 {
    grid-template-columns: repeat(3, 1fr);
  }
  .gallery--columns-4 {
    grid-template-columns: repeat(4, 1fr);
  }
}

.gallery__item {
  margin: 0;
}

.gallery__img {
  width: 100%;
  height: 12rem;
  object-fit: cover;
  border-radius: 0.5rem;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s ease;
}

.gallery__item:hover .gallery__img {
  transform: scale(1.05);
}

.gallery__caption {
  margin-top: 0.5rem;
  text-align: center;
  font-size: 0.75rem;
  color: #6b7280;
}

/* -----------------------------------------------------------------------------
   VIDEO EMBED
   ----------------------------------------------------------------------------- */

.video-embed {
  margin: 2rem 0;
}

.video-embed__wrapper {
  position: relative;
  padding-bottom: 56.25%; /* 16:9 default */
  height: 0;
  overflow: hidden;
  border-radius: 0.75rem;
  background: black;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
}

.video-embed--4-3 .video-embed__wrapper {
  padding-bottom: 75%;
}

.video-embed--1-1 .video-embed__wrapper {
  padding-bottom: 100%;
}

.video-embed__iframe {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.video-embed__caption {
  margin-top: 0.75rem;
  text-align: center;
  font-size: 0.875rem;
  color: #6b7280;
}

.video-embed--error {
  padding: 1rem;
  background: #fef2f2;
  border-radius: 0.5rem;
  color: #dc2626;
}

/* -----------------------------------------------------------------------------
   EMBED (Social Media)
   ----------------------------------------------------------------------------- */

.embed {
  margin: 2rem 0;
}

.embed__link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  background: #f9fafb;
  border-radius: 0.75rem;
  border: 1px solid #e5e7eb;
  text-decoration: none;
  transition: border-color 0.2s ease;
}

.embed__link:hover {
  border-color: #10b981;
}

.embed__platform {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  background: #e5e7eb;
  font-size: 1rem;
  color: #374151;
}

.embed__url {
  flex: 1;
  color: #111827;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* -----------------------------------------------------------------------------
   TABLE
   ----------------------------------------------------------------------------- */

.table {
  margin: 2rem 0;
  width: 100%;
  border-collapse: collapse;
  overflow-x: auto;
  display: block;
}

@media (min-width: 768px) {
  .table {
    display: table;
  }
}

.table__caption {
  text-align: left;
  font-size: 0.875rem;
  color: #6b7280;
  margin-bottom: 0.75rem;
  caption-side: top;
}

.table__header-cell {
  padding: 0.75rem 1rem;
  text-align: left;
  font-weight: 600;
  color: #111827;
  background: #f9fafb;
  border-bottom: 2px solid #10b981;
}

.table__cell {
  padding: 0.75rem 1rem;
  color: #374151;
  border-bottom: 1px solid #e5e7eb;
}

.table--striped .table__row--odd {
  background: #f9fafb;
}

.table--hoverable .table__row:hover {
  background: #ecfdf5;
}

.table__cell a {
  color: #059669;
  text-decoration: underline;
}

.table__cell strong {
  font-weight: 600;
  color: #111827;
}

/* -----------------------------------------------------------------------------
   STATS
   ----------------------------------------------------------------------------- */

.stats {
  margin: 2rem 0;
}

.stats__title {
  font-weight: 600;
  font-size: 1.25rem;
  color: #111827;
  margin-bottom: 1.5rem;
}

.stats__grid {
  display: grid;
  gap: 1rem;
}

.stats--columns-2 .stats__grid {
  grid-template-columns: repeat(2, 1fr);
}

.stats--columns-3 .stats__grid {
  grid-template-columns: repeat(2, 1fr);
}

.stats--columns-4 .stats__grid {
  grid-template-columns: repeat(2, 1fr);
}

@media (min-width: 1024px) {
  .stats--columns-3 .stats__grid {
    grid-template-columns: repeat(3, 1fr);
  }
  .stats--columns-4 .stats__grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

.stat {
  padding: 1.5rem;
  text-align: center;
  background: linear-gradient(to bottom right, #f9fafb, #f3f4f6);
  border-radius: 0.75rem;
  border: 1px solid #e5e7eb;
}

.stat__icon {
  font-size: 1.875rem;
  margin-bottom: 0.5rem;
  display: block;
}

.stat__value {
  font-size: 2.25rem;
  font-weight: 700;
  color: #059669;
  margin-bottom: 0.25rem;
  display: block;
}

.stat__label {
  font-weight: 500;
  color: #111827;
  display: block;
}

.stat__description {
  font-size: 0.875rem;
  color: #6b7280;
  margin-top: 0.25rem;
  display: block;
}

/* -----------------------------------------------------------------------------
   ACCORDION
   ----------------------------------------------------------------------------- */

.accordion {
  margin: 2rem 0;
}

.accordion__title {
  font-weight: 600;
  font-size: 1.25rem;
  color: #111827;
  margin-bottom: 1rem;
}

.accordion__item {
  border: 1px solid #e5e7eb;
  border-radius: 0.75rem;
  overflow: hidden;
  margin-bottom: 0.75rem;
}

.accordion__question {
  width: 100%;
  padding: 1rem 1.25rem;
  background: #f9fafb;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 500;
  color: #111827;
  list-style: none;
}

.accordion__question::-webkit-details-marker {
  display: none;
}

.accordion__question::after {
  content: "▼";
  font-size: 0.75rem;
  color: #10b981;
  transition: transform 0.2s ease;
}

.accordion__item[open] .accordion__question::after {
  transform: rotate(180deg);
}

.accordion__answer {
  padding: 1rem 1.25rem;
  color: #374151;
  line-height: 1.625;
}

.accordion__answer a {
  color: #059669;
  text-decoration: underline;
}

.accordion__answer strong {
  font-weight: 600;
  color: #111827;
}

/* -----------------------------------------------------------------------------
   BUTTON
   ----------------------------------------------------------------------------- */

.button-wrapper {
  margin: 2rem 0;
}

.button-wrapper--centered {
  text-align: center;
}

.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-weight: 600;
  border-radius: 0.75rem;
  text-decoration: none;
  transition: all 0.2s ease;
}

.button:hover {
  transform: scale(1.05);
}

.button--primary {
  background: #059669;
  color: white;
  box-shadow: 0 10px 15px -3px rgba(5, 150, 105, 0.25);
}

.button--primary:hover {
  background: #047857;
}

.button--secondary {
  background: #1f2937;
  color: white;
}

.button--secondary:hover {
  background: #111827;
}

.button--outline {
  border: 2px solid #059669;
  color: #059669;
  background: transparent;
}

.button--outline:hover {
  background: #059669;
  color: white;
}

.button--ghost {
  color: #059669;
  background: transparent;
}

.button--ghost:hover {
  background: #ecfdf5;
}

.button--small {
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
}

.button--medium {
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
}

.button--large {
  padding: 1rem 2rem;
  font-size: 1.125rem;
}

/* -----------------------------------------------------------------------------
   TABLE OF CONTENTS
   ----------------------------------------------------------------------------- */

.toc {
  margin: 2rem 0;
  padding: 1.5rem;
  background: #f9fafb;
  border-radius: 0.75rem;
  border: 1px solid #e5e7eb;
}

.toc__title {
  font-weight: 600;
  color: #111827;
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.toc__list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.toc__item {
  margin-bottom: 0.5rem;
}

.toc__item--level-3 {
  padding-left: 1rem;
}

.toc__item--level-4 {
  padding-left: 2rem;
}

.toc__link {
  color: #6b7280;
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: color 0.2s ease;
}

.toc__link::before {
  content: "";
  width: 0.375rem;
  height: 0.375rem;
  border-radius: 50%;
  background: #d1d5db;
}

.toc__link:hover {
  color: #059669;
}

/* -----------------------------------------------------------------------------
   CODE BLOCK
   ----------------------------------------------------------------------------- */

.code-block {
  margin: 2rem 0;
  border-radius: 0.75rem;
  overflow: hidden;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
}

.code-block__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  background: #1f2937;
}

.code-block__header::before {
  content: "";
  display: flex;
  gap: 0.375rem;
}

.code-block__filename {
  color: #9ca3af;
  font-size: 0.875rem;
  font-family: monospace;
}

.code-block__language {
  color: #9ca3af;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.code-block__copy {
  background: transparent;
  border: none;
  color: #9ca3af;
  font-size: 0.875rem;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  transition: color 0.2s ease;
}

.code-block__copy:hover {
  color: white;
}

.code-block__pre {
  margin: 0;
  padding: 1rem;
  background: #111827;
  overflow-x: auto;
}

.code-block__code {
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 0.875rem;
  color: #f9fafb;
  line-height: 1.625;
}

.code-block--line-numbers .code-block__line {
  display: table-row;
}

.code-block__line-number {
  display: table-cell;
  padding-right: 1rem;
  text-align: right;
  color: #6b7280;
  user-select: none;
  width: 2rem;
}

.code-block__line-content {
  display: table-cell;
  white-space: pre-wrap;
  word-break: break-word;
}

/* -----------------------------------------------------------------------------
   CALLOUT
   ----------------------------------------------------------------------------- */

.callout {
  margin: 2rem 0;
  border-radius: 0.75rem;
  border-left-width: 4px;
  overflow: hidden;
}

.callout__header {
  padding: 1rem 1.25rem 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.callout__icon {
  font-size: 1rem;
}

.callout__title {
  font-weight: 600;
}

.callout__content {
  padding: 0.25rem 1.25rem 1rem;
  color: #374151;
}

.callout__content a {
  color: #059669;
  text-decoration: underline;
}

.callout__content strong {
  font-weight: 600;
  color: #111827;
}

/* Callout variants */
.callout--tip {
  background: #ecfdf5;
  border-left-color: #10b981;
}

.callout--tip .callout__title {
  color: #047857;
}

.callout--info {
  background: #eff6ff;
  border-left-color: #3b82f6;
}

.callout--info .callout__title {
  color: #1d4ed8;
}

.callout--warning {
  background: #fffbeb;
  border-left-color: #f59e0b;
}

.callout--warning .callout__title {
  color: #b45309;
}

.callout--success {
  background: #ecfdf5;
  border-left-color: #10b981;
}

.callout--success .callout__title {
  color: #047857;
}

.callout--error {
  background: #fef2f2;
  border-left-color: #ef4444;
}

.callout--error .callout__title {
  color: #dc2626;
}

.callout--note {
  background: #f9fafb;
  border-left-color: #9ca3af;
}

.callout--note .callout__title {
  color: #374151;
}

/* -----------------------------------------------------------------------------
   DIVIDER
   ----------------------------------------------------------------------------- */

.divider {
  margin: 2.5rem 0;
  border: none;
}

.divider--solid {
  border-top: 1px solid #e5e7eb;
}

.divider--dashed {
  border-top: 1px dashed #d1d5db;
}

.divider--dotted {
  border-top: 1px dotted #d1d5db;
}

.divider--gradient {
  height: 1px;
  background: linear-gradient(to right, transparent, #d1d5db, transparent);
}

/* -----------------------------------------------------------------------------
   DARK MODE (Optional)
   Add if your theme supports dark mode
   ----------------------------------------------------------------------------- */

@media (prefers-color-scheme: dark) {
  .blog-paragraph {
    color: #d1d5db;
  }

  .blog-paragraph strong,
  .blog-heading,
  .quote__attribution,
  .checklist__title,
  .pros-cons__title,
  .stats__title,
  .stat__label,
  .accordion__title,
  .accordion__question,
  .accordion__answer strong,
  .toc__title,
  .callout__content strong,
  .table__header-cell,
  .table__cell strong {
    color: #f9fafb;
  }

  .quote,
  .checklist,
  .embed__link,
  .toc {
    background: #1f2937;
    border-color: #374151;
  }

  .quote__text,
  .list__item,
  .checklist__text,
  .table__cell,
  .stat__description,
  .accordion__answer,
  .toc__link,
  .callout__content {
    color: #d1d5db;
  }

  .table__header-cell,
  .accordion__question {
    background: #111827;
  }

  .stat {
    background: linear-gradient(to bottom right, #1f2937, #111827);
    border-color: #374151;
  }
}
```

## Liquid Template Updates for SEO Metafields

To use the SEO metafields synced from Supabase, update your theme's Liquid templates.

### Option 1: Update theme.liquid

Add this to the `<head>` section of your `layout/theme.liquid`:

```liquid
{% comment %}
  Custom SEO from Supabase metafields
{% endcomment %}
{%- if template.name == 'article' -%}
  {%- if article.metafields.seo.title != blank -%}
    <title>{{ article.metafields.seo.title }}</title>
  {%- endif -%}

  {%- if article.metafields.seo.description != blank -%}
    <meta name="description" content="{{ article.metafields.seo.description | escape }}">
  {%- endif -%}

  {%- if article.metafields.seo.keywords != blank -%}
    <meta name="keywords" content="{{ article.metafields.seo.keywords | escape }}">
  {%- endif -%}
{%- endif -%}
```

### Option 2: Create a snippet

Create a new file `snippets/article-seo.liquid`:

```liquid
{% comment %}
  Article SEO from Supabase metafields
  Usage: {% render 'article-seo' %}
{% endcomment %}

{%- if article.metafields.seo.title != blank -%}
  <title>{{ article.metafields.seo.title }}</title>
{%- else -%}
  <title>{{ article.title }} | {{ shop.name }}</title>
{%- endif -%}

{%- if article.metafields.seo.description != blank -%}
  <meta name="description" content="{{ article.metafields.seo.description | escape }}">
{%- else -%}
  <meta name="description" content="{{ article.excerpt | strip_html | truncate: 160 | escape }}">
{%- endif -%}

{%- if article.metafields.seo.keywords != blank -%}
  <meta name="keywords" content="{{ article.metafields.seo.keywords | escape }}">
{%- endif -%}

{% comment %} Open Graph tags {% endcomment %}
<meta property="og:title" content="{{ article.metafields.seo.title | default: article.title | escape }}">
<meta property="og:description" content="{{ article.metafields.seo.description | default: article.excerpt | strip_html | truncate: 200 | escape }}">
<meta property="og:type" content="article">
<meta property="og:url" content="{{ canonical_url }}">
{%- if article.image -%}
  <meta property="og:image" content="{{ article.image | image_url: width: 1200 }}">
{%- endif -%}

{% comment %} Twitter Card tags {% endcomment %}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{{ article.metafields.seo.title | default: article.title | escape }}">
<meta name="twitter:description" content="{{ article.metafields.seo.description | default: article.excerpt | strip_html | truncate: 200 | escape }}">
```

Then include it in your `theme.liquid`:

```liquid
{%- if template.name == 'article' -%}
  {% render 'article-seo' %}
{%- endif -%}
```

## Block Type Reference

| Block Type | CSS Class | Description |
|------------|-----------|-------------|
| paragraph | `.blog-paragraph` | Basic text content |
| heading | `.blog-heading`, `.blog-heading--h2/h3/h4` | Section headings |
| quote | `.quote` | Blockquotes with attribution |
| list | `.list`, `.list--ordered/unordered` | Bullet or numbered lists |
| checklist | `.checklist` | Checkbox items |
| proscons | `.pros-cons` | Pros/cons comparison grid |
| image | `.image`, `.image--small/medium/large/full` | Single images |
| gallery | `.gallery`, `.gallery--columns-2/3/4` | Image grids |
| video | `.video-embed` | YouTube/Vimeo embeds |
| embed | `.embed` | Social media embeds |
| table | `.table` | Data tables |
| stats | `.stats` | Statistics showcase |
| accordion | `.accordion` | Collapsible FAQ items |
| button | `.button`, `.button--primary/secondary/outline/ghost` | CTA buttons |
| tableOfContents | `.toc` | Navigation TOC |
| code | `.code-block` | Code snippets |
| callout | `.callout`, `.callout--tip/info/warning/success/error/note` | Highlighted boxes |
| divider | `.divider`, `.divider--solid/dashed/dotted/gradient` | Horizontal rules |
