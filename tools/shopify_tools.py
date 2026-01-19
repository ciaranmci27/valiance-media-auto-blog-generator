"""
Shopify Tools - Core functions for syncing blog content to Shopify

This module provides:
1. HTML rendering for all 19 content block types
2. Shopify GraphQL API integration
3. Category-to-Blog and Post-to-Article sync functions
4. SEO metafield management
"""

import json
import re
import html
from typing import Optional, Any
from datetime import datetime, timedelta
import aiohttp
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SUPABASE_URL,
    get_supabase_headers,
    SHOPIFY_STORE,
    SHOPIFY_CLIENT_ID,
    SHOPIFY_CLIENT_SECRET,
    SHOPIFY_API_VERSION,
    SHOPIFY_DEFAULT_AUTHOR,
)


# =============================================================================
# OAUTH TOKEN MANAGEMENT
# =============================================================================

class ShopifyTokenManager:
    """
    Manages OAuth access tokens for Shopify API.

    Tokens are obtained via client credentials grant and cached until expiry.
    Tokens are automatically refreshed when they expire (24 hour lifetime).
    """

    def __init__(self):
        self._access_token: Optional[str] = None
        self._expires_at: Optional[datetime] = None

    def is_token_valid(self) -> bool:
        """Check if current token is valid and not expired."""
        if not self._access_token or not self._expires_at:
            return False
        # Refresh 5 minutes before expiry to avoid edge cases
        return datetime.utcnow() < (self._expires_at - timedelta(minutes=5))

    async def get_access_token(self) -> Optional[str]:
        """
        Get a valid access token, refreshing if necessary.

        Returns:
            Access token string, or None if unable to obtain token
        """
        if self.is_token_valid():
            return self._access_token

        # Need to fetch a new token
        return await self._fetch_new_token()

    async def _fetch_new_token(self) -> Optional[str]:
        """
        Fetch a new access token using client credentials grant.

        Returns:
            Access token string, or None if request failed
        """
        if not SHOPIFY_STORE or not SHOPIFY_CLIENT_ID or not SHOPIFY_CLIENT_SECRET:
            print("Error: Shopify credentials not configured")
            return None

        token_url = f"https://{SHOPIFY_STORE}.myshopify.com/admin/oauth/access_token"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": SHOPIFY_CLIENT_ID,
                        "client_secret": SHOPIFY_CLIENT_SECRET,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        print(f"Error fetching Shopify token: {resp.status} - {error_text}")
                        return None

                    result = await resp.json()

                    self._access_token = result.get("access_token")
                    expires_in = result.get("expires_in", 86400)  # Default 24 hours
                    self._expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

                    return self._access_token

        except aiohttp.ClientError as e:
            print(f"Network error fetching Shopify token: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error fetching Shopify token: {e}")
            return None


# Global token manager instance
_token_manager = ShopifyTokenManager()


# =============================================================================
# STATUS HELPER FUNCTIONS
# =============================================================================

def get_shopify_publish_settings(status: str, scheduled_at: Optional[str] = None) -> dict:
    """
    Convert Supabase status to Shopify publish settings.
    All statuses are synced - this determines visibility in Shopify.

    Args:
        status: Post status ('draft', 'archived', 'published', or 'scheduled')
        scheduled_at: ISO 8601 datetime string for scheduled posts

    Returns:
        Dict with 'isPublished' and optionally 'publishDate'

    Mapping:
        - draft/archived -> Hidden (isPublished: false)
        - published -> Visible (isPublished: true)
        - scheduled -> Scheduled (isPublished: true + future publishDate)
    """
    if status == 'published':
        return {
            'isPublished': True,
        }

    elif status == 'scheduled':
        if scheduled_at:
            return {
                'isPublished': True,  # Must be True for scheduling to work
                'publishDate': scheduled_at,  # ISO 8601 format, future date triggers "Scheduled"
            }
        else:
            # Scheduled without a date - treat as published
            print("Warning: 'scheduled' status without scheduled_at, treating as published")
            return {
                'isPublished': True,
            }

    elif status in ('draft', 'archived'):
        return {
            'isPublished': False,  # Hidden in Shopify
        }

    # Unknown status - default to hidden for safety
    return {
        'isPublished': False,
    }


def get_shopify_visibility_label(status: str) -> str:
    """Get human-readable Shopify visibility for a given status."""
    mapping = {
        'draft': 'Hidden',
        'archived': 'Hidden',
        'published': 'Visible',
        'scheduled': 'Scheduled',
    }
    return mapping.get(status, 'Hidden')


# =============================================================================
# HTML ESCAPE UTILITIES
# =============================================================================

def escape_html(text: str) -> str:
    """Escape HTML special characters for safe output."""
    return html.escape(text)


def generate_anchor_id(text: str) -> str:
    """Generate a URL-safe anchor ID from heading text."""
    # Strip HTML tags first
    clean_text = re.sub(r'<[^>]*>', '', text)
    # Convert to lowercase, replace non-alphanumeric with hyphens
    anchor = re.sub(r'[^a-z0-9]+', '-', clean_text.lower())
    # Remove leading/trailing hyphens
    return anchor.strip('-')


# =============================================================================
# CONTENT BLOCK TO HTML RENDERER
# =============================================================================

def render_blocks_to_html(blocks: list) -> str:
    """
    Convert an array of content blocks to HTML string.

    This produces HTML that matches the structure and CSS classes
    used in the headless frontend (ContentBlockRenderer.tsx).

    Args:
        blocks: List of content block dictionaries

    Returns:
        HTML string suitable for Shopify article body
    """
    if not blocks or not isinstance(blocks, list):
        return ''

    html_parts = []

    for block in blocks:
        if not block or not isinstance(block, dict):
            continue

        block_type = block.get('type', '')

        # Handle two block formats:
        # 1. Standard format: {"type": "paragraph", "data": {"text": "..."}}
        # 2. Import format: {"type": "html", "content": "..."}
        data = block.get('data', {})

        # For imported HTML blocks, content is directly on block, not in 'data'
        if block_type == 'html' and not data:
            data = {'content': block.get('content', '')}

        try:
            rendered = render_block(block_type, data, blocks)
            if rendered:
                html_parts.append(rendered)
        except Exception as e:
            # Skip malformed blocks with warning, don't fail entire sync
            print(f"Warning: Failed to render block type '{block_type}': {e}")
            continue

    return '\n\n'.join(html_parts)


def render_block(block_type: str, data: dict, all_blocks: list = None) -> str:
    """Render a single content block to HTML."""

    if block_type == 'paragraph':
        return render_paragraph(data)
    elif block_type == 'heading':
        return render_heading(data)
    elif block_type == 'quote':
        return render_quote(data)
    elif block_type == 'list':
        return render_list(data)
    elif block_type == 'checklist':
        return render_checklist(data)
    elif block_type == 'proscons':
        return render_proscons(data)
    elif block_type == 'image':
        return render_image(data)
    elif block_type == 'gallery':
        return render_gallery(data)
    elif block_type == 'video':
        return render_video(data)
    elif block_type == 'embed':
        return render_embed(data)
    elif block_type == 'table':
        return render_table(data)
    elif block_type == 'stats':
        return render_stats(data)
    elif block_type == 'accordion':
        return render_accordion(data)
    elif block_type == 'button':
        return render_button(data)
    elif block_type == 'tableOfContents':
        return render_table_of_contents(data, all_blocks)
    elif block_type == 'code':
        return render_code(data)
    elif block_type == 'callout':
        return render_callout(data)
    elif block_type == 'divider':
        return render_divider(data)
    elif block_type == 'widget':
        return render_widget(data)
    elif block_type == 'html':
        # Raw HTML block - used by imports from Shopify
        # Content may be in data['html'] or data['content'] depending on source
        html_content = data.get('html') or data.get('content', '')
        return html_content if html_content else ''
    else:
        return ''


# =============================================================================
# INDIVIDUAL BLOCK RENDERERS
# =============================================================================

def render_paragraph(data: dict) -> str:
    """Render paragraph block - basic text content."""
    text = data.get('text', '')
    if not text:
        return ''
    # Text may contain inline HTML (strong, em, a), pass through
    return f'<p class="blog-paragraph">{text}</p>'


def render_heading(data: dict) -> str:
    """Render heading block - h2, h3, h4 with anchor."""
    text = data.get('text', '')
    level = data.get('level', 2)
    anchor = data.get('anchor', '')

    if not text:
        return ''

    # Clamp level to 2-4
    level = max(2, min(4, level))

    # Generate anchor ID if not provided
    if not anchor:
        anchor = generate_anchor_id(text)

    return f'<h{level} id="{anchor}" class="blog-heading blog-heading--h{level}">{text}</h{level}>'


def render_quote(data: dict) -> str:
    """Render quote block - blockquote with optional attribution."""
    text = data.get('text', '')
    attribution = data.get('attribution', '')
    role = data.get('role', '')

    if not text:
        return ''

    footer_html = ''
    if attribution:
        role_html = f', <span class="quote__role">{escape_html(role)}</span>' if role else ''
        footer_html = f'\n  <footer class="quote__footer"><span class="quote__attribution">{escape_html(attribution)}</span>{role_html}</footer>'

    return f'''<blockquote class="quote">
  <p class="quote__text">{text}</p>{footer_html}
</blockquote>'''


def render_list(data: dict) -> str:
    """Render list block - ordered or unordered."""
    style = data.get('style', 'unordered')
    items = data.get('items', [])

    if not items:
        return ''

    if style == 'ordered':
        items_html = '\n'.join([
            f'    <li class="list__item list__item--ordered"><span class="list__number">{i+1}</span><span class="list__content">{item}</span></li>'
            for i, item in enumerate(items) if item
        ])
        return f'<ol class="list list--ordered">\n{items_html}\n</ol>'
    else:
        items_html = '\n'.join([
            f'    <li class="list__item list__item--unordered"><span class="list__bullet"></span><span class="list__content">{item}</span></li>'
            for item in items if item
        ])
        return f'<ul class="list list--unordered">\n{items_html}\n</ul>'


def render_checklist(data: dict) -> str:
    """Render checklist block - checkbox items with optional title."""
    title = data.get('title', '')
    items = data.get('items', [])

    if not items:
        return ''

    title_html = f'<h4 class="checklist__title">{escape_html(title)}</h4>\n' if title else ''

    items_html = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = item.get('text', '')
        checked = item.get('checked', False)
        checked_class = ' checklist__item--checked' if checked else ''
        check_icon = '<span class="checklist__check">&#10003;</span>' if checked else '<span class="checklist__check checklist__check--empty"></span>'
        items_html.append(f'    <li class="checklist__item{checked_class}">{check_icon}<span class="checklist__text">{escape_html(text)}</span></li>')

    return f'''<div class="checklist">
  {title_html}<ul class="checklist__list">
{chr(10).join(items_html)}
  </ul>
</div>'''


def render_proscons(data: dict) -> str:
    """Render pros/cons block - comparison grid."""
    title = data.get('title', '')
    pros = data.get('pros', [])
    cons = data.get('cons', [])

    if not pros and not cons:
        return ''

    title_html = f'<h4 class="pros-cons__title">{escape_html(title)}</h4>\n' if title else ''

    pros_items = '\n'.join([f'        <li class="pros-cons__item pros-cons__item--pro"><span class="pros-cons__icon">+</span>{item}</li>' for item in pros if item])
    cons_items = '\n'.join([f'        <li class="pros-cons__item pros-cons__item--con"><span class="pros-cons__icon">-</span>{item}</li>' for item in cons if item])

    return f'''<div class="pros-cons">
  {title_html}<div class="pros-cons__grid">
    <div class="pros-cons__section pros-cons__section--pros">
      <h5 class="pros-cons__heading pros-cons__heading--pros"><span class="pros-cons__badge">&#10003;</span>Pros</h5>
      <ul class="pros-cons__list">
{pros_items}
      </ul>
    </div>
    <div class="pros-cons__section pros-cons__section--cons">
      <h5 class="pros-cons__heading pros-cons__heading--cons"><span class="pros-cons__badge">&#10005;</span>Cons</h5>
      <ul class="pros-cons__list">
{cons_items}
      </ul>
    </div>
  </div>
</div>'''


def render_image(data: dict) -> str:
    """Render image block - single image with optional caption."""
    src = data.get('src', '')
    alt = data.get('alt', '')
    caption = data.get('caption', '')
    size = data.get('size', 'large')

    if not src:
        return ''

    caption_html = f'\n  <figcaption class="image__caption">{escape_html(caption)}</figcaption>' if caption else ''

    return f'''<figure class="image image--{size}">
  <img src="{escape_html(src)}" alt="{escape_html(alt)}" class="image__img" loading="lazy" />{caption_html}
</figure>'''


def render_gallery(data: dict) -> str:
    """Render gallery block - image grid."""
    images = data.get('images', [])
    columns = data.get('columns', 3)

    if not images:
        return ''

    images_html = []
    for img in images:
        if not isinstance(img, dict):
            continue
        src = img.get('src', '')
        alt = img.get('alt', '')
        caption = img.get('caption', '')

        if not src:
            continue

        caption_html = f'\n      <figcaption class="gallery__caption">{escape_html(caption)}</figcaption>' if caption else ''
        images_html.append(f'''    <figure class="gallery__item">
      <img src="{escape_html(src)}" alt="{escape_html(alt)}" class="gallery__img" loading="lazy" />{caption_html}
    </figure>''')

    return f'''<div class="gallery gallery--columns-{columns}">
{chr(10).join(images_html)}
</div>'''


def render_video(data: dict) -> str:
    """Render video block - YouTube/Vimeo embed."""
    url = data.get('url', '')
    caption = data.get('caption', '')
    aspect_ratio = data.get('aspectRatio', '16:9')

    if not url:
        return ''

    # Extract embed URL from YouTube or Vimeo
    embed_url = None

    # YouTube patterns
    youtube_match = re.search(r'(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})', url)
    if youtube_match:
        embed_url = f'https://www.youtube.com/embed/{youtube_match.group(1)}'

    # Vimeo patterns
    if not embed_url:
        vimeo_match = re.search(r'vimeo\.com\/(\d+)', url)
        if vimeo_match:
            embed_url = f'https://player.vimeo.com/video/{vimeo_match.group(1)}'

    if not embed_url:
        return f'<div class="video-embed video-embed--error">Invalid video URL: {escape_html(url)}</div>'

    aspect_class = aspect_ratio.replace(':', '-')
    caption_html = f'\n  <figcaption class="video-embed__caption">{escape_html(caption)}</figcaption>' if caption else ''

    return f'''<figure class="video-embed video-embed--{aspect_class}">
  <div class="video-embed__wrapper">
    <iframe src="{embed_url}" class="video-embed__iframe" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
  </div>{caption_html}
</figure>'''


def render_embed(data: dict) -> str:
    """Render embed block - social media embeds."""
    platform = data.get('platform', 'other')
    url = data.get('url', '')
    embed_html = data.get('html', '')

    # If custom HTML provided, use it
    if embed_html:
        return f'<div class="embed embed--{platform}">{embed_html}</div>'

    if not url:
        return ''

    # Otherwise render as a link card
    platform_icons = {
        'twitter': 'X',
        'instagram': 'Instagram',
        'tiktok': 'TikTok',
        'facebook': 'Facebook',
        'other': 'Link',
    }
    platform_name = platform_icons.get(platform, 'Link')

    return f'''<div class="embed embed--{platform}">
  <a href="{escape_html(url)}" target="_blank" rel="noopener noreferrer" class="embed__link">
    <span class="embed__platform">{platform_name}</span>
    <span class="embed__url">{escape_html(url)}</span>
  </a>
</div>'''


def render_table(data: dict) -> str:
    """Render table block - data table with optional styling."""
    caption = data.get('caption', '')
    headers = data.get('headers', [])
    rows = data.get('rows', [])
    striped = data.get('striped', True)
    hoverable = data.get('hoverable', True)

    if not headers and not rows:
        return ''

    classes = ['table']
    if striped:
        classes.append('table--striped')
    if hoverable:
        classes.append('table--hoverable')

    caption_html = f'  <caption class="table__caption">{escape_html(caption)}</caption>\n' if caption else ''

    header_cells = ''.join([f'<th class="table__header-cell">{cell}</th>' for cell in headers])
    header_html = f'  <thead class="table__head"><tr class="table__row table__row--header">{header_cells}</tr></thead>\n' if headers else ''

    body_rows = []
    for i, row in enumerate(rows):
        if not isinstance(row, list):
            continue
        cells = ''.join([f'<td class="table__cell">{cell}</td>' for cell in row])
        row_class = 'table__row--even' if i % 2 == 0 else 'table__row--odd'
        body_rows.append(f'    <tr class="table__row {row_class}">{cells}</tr>')

    body_html = f'  <tbody class="table__body">\n{chr(10).join(body_rows)}\n  </tbody>' if body_rows else ''

    return f'''<table class="{' '.join(classes)}">
{caption_html}{header_html}{body_html}
</table>'''


def render_stats(data: dict) -> str:
    """Render stats block - statistics showcase grid."""
    title = data.get('title', '')
    stats = data.get('stats', [])
    columns = data.get('columns', 3)

    if not stats:
        return ''

    title_html = f'<h4 class="stats__title">{escape_html(title)}</h4>\n' if title else ''

    stat_items = []
    for stat in stats:
        if not isinstance(stat, dict):
            continue
        value = stat.get('value', '')
        label = stat.get('label', '')
        description = stat.get('description', '')
        icon = stat.get('icon', '')

        icon_html = f'<span class="stat__icon">{icon}</span>' if icon else ''
        desc_html = f'<span class="stat__description">{escape_html(description)}</span>' if description else ''

        stat_items.append(f'''    <div class="stat">
      {icon_html}<span class="stat__value">{escape_html(value)}</span>
      <span class="stat__label">{escape_html(label)}</span>
      {desc_html}
    </div>''')

    return f'''<div class="stats stats--columns-{columns}">
  {title_html}<div class="stats__grid">
{chr(10).join(stat_items)}
  </div>
</div>'''


def render_accordion(data: dict) -> str:
    """Render accordion block - collapsible FAQ items."""
    title = data.get('title', '')
    items = data.get('items', [])
    default_open = data.get('defaultOpen')

    if not items:
        return ''

    title_html = f'<h4 class="accordion__title">{escape_html(title)}</h4>\n' if title else ''

    accordion_items = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        question = item.get('question', '')
        answer = item.get('answer', '')

        open_attr = ' open' if i == default_open else ''

        accordion_items.append(f'''    <details class="accordion__item"{open_attr}>
      <summary class="accordion__question">{escape_html(question)}</summary>
      <div class="accordion__answer">{answer}</div>
    </details>''')

    return f'''<div class="accordion">
  {title_html}{chr(10).join(accordion_items)}
</div>'''


def render_button(data: dict) -> str:
    """Render button block - CTA button."""
    text = data.get('text', '')
    url = data.get('url', '#')
    style = data.get('style', 'primary')
    size = data.get('size', 'medium')
    icon = data.get('icon', '')
    new_tab = data.get('newTab', False)
    centered = data.get('centered', True)

    if not text:
        return ''

    target_attr = ' target="_blank" rel="noopener noreferrer"' if new_tab else ''
    icon_html = f'<span class="button__icon">{icon}</span>' if icon else ''
    wrapper_class = 'button-wrapper button-wrapper--centered' if centered else 'button-wrapper'

    return f'''<div class="{wrapper_class}">
  <a href="{escape_html(url)}" class="button button--{style} button--{size}"{target_attr}>
    {icon_html}<span class="button__text">{escape_html(text)}</span>
  </a>
</div>'''


def render_table_of_contents(data: dict, all_blocks: list = None) -> str:
    """Render table of contents block."""
    title = data.get('title', 'Table of Contents')
    items = data.get('items', [])
    auto_generate = data.get('autoGenerate', False)

    # Auto-generate from headings if requested
    if auto_generate and all_blocks:
        items = []
        for block in all_blocks:
            if block.get('type') == 'heading':
                block_data = block.get('data', {})
                text = block_data.get('text', '')
                # Strip HTML tags from text for display
                clean_text = re.sub(r'<[^>]*>', '', text)
                anchor = block_data.get('anchor', generate_anchor_id(text))
                level = block_data.get('level', 2)
                items.append({'text': clean_text, 'anchor': anchor, 'level': level})

    if not items:
        return ''

    toc_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = item.get('text', '')
        anchor = item.get('anchor', '')
        level = item.get('level', 2)

        indent_class = f'toc__item--level-{level}'
        toc_items.append(f'    <li class="toc__item {indent_class}"><a href="#{escape_html(anchor)}" class="toc__link">{escape_html(text)}</a></li>')

    return f'''<nav class="toc">
  <h4 class="toc__title">{escape_html(title)}</h4>
  <ul class="toc__list">
{chr(10).join(toc_items)}
  </ul>
</nav>'''


def render_code(data: dict) -> str:
    """Render code block - code snippet with optional line numbers."""
    language = data.get('language', '')
    code = data.get('code', '')
    filename = data.get('filename', '')
    show_line_numbers = data.get('showLineNumbers', False)

    if not code:
        return ''

    lang_class = f' language-{language}' if language else ''
    filename_html = f'<div class="code-block__filename">{escape_html(filename)}</div>' if filename else ''
    lang_label = f'<span class="code-block__language">{language}</span>' if language and not filename else ''

    # Escape the code content
    escaped_code = escape_html(code)

    if show_line_numbers:
        lines = escaped_code.split('\n')
        numbered_lines = []
        for i, line in enumerate(lines, 1):
            numbered_lines.append(f'<span class="code-block__line"><span class="code-block__line-number">{i}</span><span class="code-block__line-content">{line}</span></span>')
        code_content = '\n'.join(numbered_lines)
        line_numbers_class = ' code-block--line-numbers'
    else:
        code_content = escaped_code
        line_numbers_class = ''

    return f'''<div class="code-block{line_numbers_class}">
  <div class="code-block__header">
    {filename_html}{lang_label}
    <button class="code-block__copy" onclick="navigator.clipboard.writeText(this.closest('.code-block').querySelector('code').textContent)">Copy</button>
  </div>
  <pre class="code-block__pre"><code class="code-block__code{lang_class}">{code_content}</code></pre>
</div>'''


def render_callout(data: dict) -> str:
    """Render callout block - tip/info/warning/success/error/note boxes."""
    style = data.get('style', 'info')
    title = data.get('title', '')
    text = data.get('text', '')

    if not text:
        return ''

    # Default titles and icons for each style
    defaults = {
        'tip': {'title': 'Pro Tip', 'icon': '&#128161;'},  # lightbulb
        'info': {'title': 'Info', 'icon': '&#8505;'},  # info
        'warning': {'title': 'Warning', 'icon': '&#9888;'},  # warning
        'success': {'title': 'Success', 'icon': '&#10003;'},  # checkmark
        'error': {'title': 'Error', 'icon': '&#10005;'},  # x
        'note': {'title': 'Note', 'icon': '&#128221;'},  # memo
    }

    default_config = defaults.get(style, defaults['info'])
    display_title = title if title else default_config['title']
    icon = default_config['icon']

    return f'''<div class="callout callout--{style}">
  <div class="callout__header">
    <span class="callout__icon">{icon}</span>
    <span class="callout__title">{escape_html(display_title)}</span>
  </div>
  <div class="callout__content">{text}</div>
</div>'''


def render_divider(data: dict) -> str:
    """Render divider block - horizontal rule with style variations."""
    style = data.get('style', 'solid')

    if style == 'gradient':
        return '<div class="divider divider--gradient"></div>'

    return f'<hr class="divider divider--{style}" />'


def render_widget(data: dict) -> str:
    """Render widget block - custom widget placeholder (renders as comment)."""
    widget_type = data.get('widgetType', 'unknown')
    return f'<!-- Widget: {escape_html(widget_type)} -->'


# =============================================================================
# SEO METAFIELDS BUILDER
# =============================================================================

def build_seo_metafields(seo_data: dict) -> list:
    """
    Build Shopify metafields array from Supabase SEO data.

    Args:
        seo_data: Dict with keys like 'title', 'description', 'keywords', 'image'

    Returns:
        List of metafield objects for Shopify GraphQL API
    """
    if not seo_data:
        return []

    metafields = []

    # SEO Title
    if seo_data.get('title'):
        metafields.append({
            "namespace": "seo",
            "key": "title",
            "value": str(seo_data['title']),
            "type": "single_line_text_field"
        })

    # SEO Description
    if seo_data.get('description'):
        metafields.append({
            "namespace": "seo",
            "key": "description",
            "value": str(seo_data['description']),
            "type": "single_line_text_field"
        })

    # SEO Keywords
    if seo_data.get('keywords'):
        keywords = seo_data['keywords']
        if isinstance(keywords, list):
            keywords = ", ".join(keywords)
        metafields.append({
            "namespace": "seo",
            "key": "keywords",
            "value": str(keywords),
            "type": "single_line_text_field"
        })

    return metafields


async def set_resource_metafields(owner_id: str, metafields: list) -> dict:
    """
    Set metafields on a Shopify resource using metafieldsSet mutation.

    This works for blogs, articles, products, collections, etc.

    Args:
        owner_id: The GID of the resource (e.g., "gid://shopify/Blog/123")
        metafields: List of metafield dicts with namespace, key, value, type

    Returns:
        dict with success status and any errors
    """
    if not metafields:
        return {"success": True}

    # Add ownerId to each metafield
    metafields_input = []
    for mf in metafields:
        metafields_input.append({
            "ownerId": owner_id,
            "namespace": mf["namespace"],
            "key": mf["key"],
            "value": mf["value"],
            "type": mf["type"],
        })

    query = """
    mutation SetMetafields($metafields: [MetafieldsSetInput!]!) {
        metafieldsSet(metafields: $metafields) {
            metafields {
                id
                namespace
                key
            }
            userErrors {
                code
                field
                message
            }
        }
    }
    """

    variables = {"metafields": metafields_input}
    result = await execute_shopify_graphql(query, variables)

    if "error" in result:
        return {"success": False, "error": result["error"]}

    set_result = result.get("metafieldsSet", {})
    user_errors = set_result.get("userErrors", [])

    if user_errors:
        error_msg = "; ".join([e.get("message", str(e)) for e in user_errors])
        return {"success": False, "error": error_msg}

    return {"success": True, "metafields": set_result.get("metafields", [])}


# =============================================================================
# SHOPIFY GRAPHQL API HELPERS
# =============================================================================

def get_shopify_graphql_url() -> str:
    """Get the Shopify GraphQL Admin API URL."""
    return f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/graphql.json"


async def get_shopify_headers() -> Optional[dict]:
    """
    Get headers for Shopify API calls with a valid access token.

    Returns:
        Headers dict with access token, or None if token unavailable
    """
    access_token = await _token_manager.get_access_token()
    if not access_token:
        return None

    return {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token,
    }


async def execute_shopify_graphql(query: str, variables: dict = None) -> dict:
    """
    Execute a GraphQL query against Shopify Admin API.

    Args:
        query: GraphQL query string
        variables: Query variables dict

    Returns:
        Response data or error dict
    """
    if not SHOPIFY_STORE or not SHOPIFY_CLIENT_ID or not SHOPIFY_CLIENT_SECRET:
        return {"error": "Shopify credentials not configured"}

    headers = await get_shopify_headers()
    if not headers:
        return {"error": "Failed to obtain Shopify access token"}

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                get_shopify_graphql_url(),
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                result = await resp.json()

                # Check for top-level errors
                if "errors" in result:
                    error_messages = [e.get("message", str(e)) for e in result["errors"]]
                    return {"error": "; ".join(error_messages)}

                return result.get("data", {})

    except aiohttp.ClientError as e:
        return {"error": f"Network error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


# =============================================================================
# SHOPIFY LOOKUP FUNCTIONS (Duplicate Prevention)
# =============================================================================

# In-memory cache to prevent race conditions during a single sync session
_blog_cache: dict[str, str] = {}  # handle -> gid
_article_cache: dict[str, str] = {}  # (blog_gid, handle) -> article_gid


async def fetch_all_shopify_blogs() -> list:
    """
    Fetch all blogs from Shopify.

    Returns a list of blog dicts with: id (gid), title, handle
    Uses cursor-based pagination.

    Returns:
        List of Shopify blog dicts, or empty list on error
    """
    all_blogs = []
    cursor = None
    page_size = 100

    while True:
        # Build query with optional cursor
        after_clause = f', after: "{cursor}"' if cursor else ""

        query = f"""
        query FetchBlogs {{
            blogs(first: {page_size}{after_clause}) {{
                pageInfo {{
                    hasNextPage
                    endCursor
                }}
                nodes {{
                    id
                    title
                    handle
                }}
            }}
        }}
        """

        result = await execute_shopify_graphql(query)

        if "error" in result:
            if not all_blogs:  # Only show error if no blogs fetched yet
                print(f"Error fetching blogs: {result['error']}")
            break

        blogs_data = result.get("blogs", {})
        nodes = blogs_data.get("nodes", [])

        if not nodes:
            break

        all_blogs.extend(nodes)

        # Check pagination
        page_info = blogs_data.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break

        cursor = page_info.get("endCursor")
        if not cursor:
            break

    return all_blogs


async def fetch_all_shopify_articles() -> list:
    """
    Fetch all articles from all blogs in Shopify.

    Returns a list of article dicts with full details including:
    id (gid), title, handle, contentHtml, excerpt, publishedAt,
    blog (gid, handle), image, tags, author

    Uses cursor-based pagination for each blog.

    Returns:
        List of Shopify article dicts, or empty list on error
    """
    # First, fetch all blogs
    blogs = await fetch_all_shopify_blogs()
    if not blogs:
        return []

    all_articles = []

    for blog in blogs:
        blog_gid = blog.get("id")
        blog_handle = blog.get("handle", "unknown")

        cursor = None
        page_size = 50

        while True:
            after_clause = f', after: "{cursor}"' if cursor else ""

            query = f"""
            query FetchArticles {{
                blog(id: "{blog_gid}") {{
                    articles(first: {page_size}{after_clause}) {{
                        pageInfo {{
                            hasNextPage
                            endCursor
                        }}
                        nodes {{
                            id
                            title
                            handle
                            body
                            summary
                            publishedAt
                            tags
                            blog {{
                                id
                                handle
                                title
                            }}
                            image {{
                                url
                                altText
                            }}
                        }}
                    }}
                }}
            }}
            """

            result = await execute_shopify_graphql(query)

            if "error" in result:
                print(f"  [WARN] Failed to fetch articles from blog '{blog_handle}': {result['error']}")
                break

            blog_data = result.get("blog", {})
            if not blog_data:
                print(f"  [WARN] No data returned for blog '{blog_handle}' - may have been deleted")
                break

            articles_data = blog_data.get("articles", {})
            nodes = articles_data.get("nodes", [])

            if not nodes:
                break

            all_articles.extend(nodes)

            # Check pagination
            page_info = articles_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break

            cursor = page_info.get("endCursor")
            if not cursor:
                break

    return all_articles


async def find_blog_by_handle(handle: str) -> Optional[str]:
    """
    Find an existing Shopify blog by handle.

    Args:
        handle: Blog handle/slug to search for

    Returns:
        Shopify blog GID if found, None otherwise
    """
    # Check in-memory cache first
    if handle in _blog_cache:
        return _blog_cache[handle]

    # Use blogs query with handle filter (blogByHandle doesn't exist in Admin API)
    query = """
    query FindBlogByHandle($query: String!) {
        blogs(first: 1, query: $query) {
            nodes {
                id
                handle
                title
            }
        }
    }
    """
    result = await execute_shopify_graphql(query, {"query": f"handle:{handle}"})

    if "error" in result:
        return None

    blogs = result.get("blogs", {}).get("nodes", [])
    if blogs:
        blog = blogs[0]
        gid = blog.get("id")
        _blog_cache[handle] = gid
        return gid

    return None


async def find_article_by_handle(blog_gid: str, handle: str) -> Optional[str]:
    """
    Find an existing Shopify article by handle within a blog.

    Args:
        blog_gid: Shopify blog GID to search in
        handle: Article handle/slug to search for

    Returns:
        Shopify article GID if found, None otherwise
    """
    cache_key = f"{blog_gid}:{handle}"
    if cache_key in _article_cache:
        return _article_cache[cache_key]

    # Query articles in this blog with matching handle
    query = """
    query FindArticle($blogId: ID!, $first: Int!, $query: String) {
        blog(id: $blogId) {
            articles(first: $first, query: $query) {
                nodes {
                    id
                    handle
                }
            }
        }
    }
    """
    result = await execute_shopify_graphql(query, {
        "blogId": blog_gid,
        "first": 1,
        "query": f"handle:{handle}"
    })

    if "error" in result:
        return None

    blog = result.get("blog")
    if blog:
        articles = blog.get("articles", {}).get("nodes", [])
        if articles:
            gid = articles[0].get("id")
            _article_cache[cache_key] = gid
            return gid

    return None


async def fetch_article_content_length(article_gid: str) -> Optional[int]:
    """
    Fetch the body content length of an existing Shopify article.

    Used for safety checks before overwriting - we should never overwrite
    a longer article with shorter content.

    Args:
        article_gid: Shopify article GID

    Returns:
        Length of article body in characters, or None if fetch failed
    """
    query = """
    query GetArticleBody($id: ID!) {
        article(id: $id) {
            id
            body
        }
    }
    """
    result = await execute_shopify_graphql(query, {"id": article_gid})

    if "error" in result:
        return None

    article = result.get("article")
    if article:
        body = article.get("body", "") or ""
        return len(body.strip())

    return None


def clear_sync_cache():
    """Clear the in-memory sync cache. Call at start of sync operations."""
    global _blog_cache, _article_cache
    _blog_cache = {}
    _article_cache = {}


# =============================================================================
# CATEGORY TO SHOPIFY BLOG SYNC
# =============================================================================

async def sync_category_to_shopify(
    category_id: str,
    name: str,
    slug: str,
    existing_blog_gid: Optional[str] = None,
    seo: Optional[dict] = None,
) -> dict:
    """
    Sync a Supabase category to a Shopify Blog.

    Note: Shopify Blog API doesn't support native SEO fields, but we can use
    metafields to store SEO data. The theme must be configured to read these.

    Args:
        category_id: Supabase category UUID
        name: Category name (becomes Blog title)
        slug: Category slug (becomes Blog handle)
        existing_blog_gid: Existing Shopify blog GID if updating
        seo: SEO data dict with keys like 'title', 'description', 'keywords'

    Returns:
        dict with keys: success, shopify_blog_gid, handle, error
    """
    # If no existing GID provided, check if blog already exists in Shopify
    if not existing_blog_gid:
        existing_blog_gid = await find_blog_by_handle(slug)
        if existing_blog_gid:
            # Blog already exists - update it instead of creating duplicate
            pass

    # Build blog input (metafields are set separately - not supported inline)
    blog_input = {
        "title": name,
        "handle": slug,
    }

    # Build SEO metafields (will be set after create/update)
    metafields = build_seo_metafields(seo)

    if existing_blog_gid:
        # Update existing blog
        query = """
        mutation UpdateBlog($id: ID!, $blog: BlogUpdateInput!) {
            blogUpdate(id: $id, blog: $blog) {
                blog { id title handle }
                userErrors { code field message }
            }
        }
        """
        variables = {
            "id": existing_blog_gid,
            "blog": blog_input,
        }

        result = await execute_shopify_graphql(query, variables)

        if "error" in result:
            # Check if this is a "not found" error - blog may have been deleted
            error_lower = result["error"].lower()
            if "not found" in error_lower or "does not exist" in error_lower:
                # Fall back to checking by handle
                existing_blog_gid = await find_blog_by_handle(slug)
                if existing_blog_gid:
                    # Retry update with correct ID
                    variables["id"] = existing_blog_gid
                    result = await execute_shopify_graphql(query, variables)
                else:
                    # Blog truly doesn't exist, create it
                    existing_blog_gid = None
            else:
                return {"success": False, "error": result["error"]}

        if existing_blog_gid:  # Still updating
            update_result = result.get("blogUpdate", {})
            user_errors = update_result.get("userErrors", [])

            if user_errors:
                # Check for "not found" type errors
                error_codes = [e.get("code", "") for e in user_errors]
                if any(code in ("INVALID", "NOT_FOUND") for code in error_codes):
                    # Stale ID - check by handle and create if needed
                    existing_blog_gid = await find_blog_by_handle(slug)
                    if not existing_blog_gid:
                        existing_blog_gid = None  # Will create below
                else:
                    error_msg = "; ".join([e.get("message", str(e)) for e in user_errors])
                    return {"success": False, "error": error_msg}
            else:
                blog = update_result.get("blog", {})
                if blog:
                    blog_gid = blog.get("id")
                    # Cache the result
                    _blog_cache[slug] = blog_gid
                    # Set metafields separately (not supported inline for blogs)
                    if metafields:
                        mf_result = await set_resource_metafields(blog_gid, metafields)
                        if not mf_result.get("success"):
                            print(f" [WARN] Metafields failed: {mf_result.get('error')}")
                    return {
                        "success": True,
                        "shopify_blog_gid": blog_gid,
                        "handle": blog.get("handle"),
                    }

    if not existing_blog_gid:
        # Create new blog (only if it truly doesn't exist)
        query = """
        mutation CreateBlog($blog: BlogCreateInput!) {
            blogCreate(blog: $blog) {
                blog { id title handle }
                userErrors { code field message }
            }
        }
        """
        variables = {
            "blog": blog_input,
        }

        result = await execute_shopify_graphql(query, variables)

        if "error" in result:
            return {"success": False, "error": result["error"]}

        create_result = result.get("blogCreate", {})
        user_errors = create_result.get("userErrors", [])

        if user_errors:
            error_msg = "; ".join([e.get("message", str(e)) for e in user_errors])
            return {"success": False, "error": error_msg}

        blog = create_result.get("blog", {})
        blog_gid = blog.get("id")
        # Cache the result
        _blog_cache[slug] = blog_gid
        # Set metafields separately (not supported inline for blogs)
        if metafields:
            mf_result = await set_resource_metafields(blog_gid, metafields)
            if not mf_result.get("success"):
                print(f" [WARN] Metafields failed: {mf_result.get('error')}")
        return {
            "success": True,
            "shopify_blog_gid": blog_gid,
            "handle": blog.get("handle"),
        }


# =============================================================================
# POST TO SHOPIFY ARTICLE SYNC
# =============================================================================

async def sync_post_to_shopify(
    post_id: str,
    title: str,
    slug: str,
    excerpt: str,
    content: list,
    status: str,
    shopify_blog_gid: str,
    author_name: Optional[str] = None,
    featured_image: Optional[str] = None,
    featured_image_alt: Optional[str] = None,
    seo: Optional[dict] = None,
    scheduled_at: Optional[str] = None,
    tags: Optional[list] = None,
    existing_shopify_id: Optional[str] = None,
) -> dict:
    """
    Sync a blog post to Shopify as an Article.

    All statuses are synced:
    - draft/archived -> Hidden in Shopify
    - published -> Visible in Shopify
    - scheduled -> Scheduled in Shopify

    Args:
        post_id: Supabase post UUID
        title: Post title
        slug: Post slug (becomes handle)
        excerpt: Post excerpt (becomes summary)
        content: JSON content blocks array
        status: Post status (draft/published/scheduled/archived)
        shopify_blog_gid: Shopify Blog GID to post to
        author_name: Author display name
        featured_image: Featured image URL
        featured_image_alt: Featured image alt text
        seo: SEO data dict
        scheduled_at: ISO 8601 datetime for scheduled posts
        tags: List of tag names
        existing_shopify_id: Existing Shopify article ID if updating

    Returns:
        dict with keys: success, shopify_article_id, handle, error
    """
    # Render content blocks to HTML
    body_html = render_blocks_to_html(content)

    # DEBUG: Log content rendering for troubleshooting
    print(f"    [DEBUG] Content blocks: {len(content) if content else 0} blocks")
    if content and len(content) > 0:
        print(f"    [DEBUG] First block type: {content[0].get('type', 'unknown')}")
        print(f"    [DEBUG] First block keys: {list(content[0].keys()) if content else 'none'}")
    print(f"    [DEBUG] Rendered HTML length: {len(body_html)} chars")

    # ==========================================================================
    # SAFETY CHECKS: Prevent accidental data loss
    # ==========================================================================
    new_content_length = len(body_html.strip()) if body_html else 0

    # Safety Check 1: Never overwrite with empty/minimal content
    if new_content_length < 50 and existing_shopify_id:
        return {
            "success": False,
            "error": f"SAFETY BLOCK: Refusing to overwrite existing Shopify article with empty/minimal content. "
                     f"New content: {new_content_length} chars (minimum 50 required). "
                     f"This protection prevents accidental data loss.",
        }

    # Safety Check 2: Never overwrite longer content with shorter content
    # This is the CRITICAL check that prevents the disaster scenario
    if existing_shopify_id:
        existing_content_length = await fetch_article_content_length(existing_shopify_id)
        if existing_content_length is not None:
            # Allow overwrite only if new content is at least 80% of existing length
            # This prevents replacing a 5000 char article with a 100 char one
            min_acceptable_length = int(existing_content_length * 0.8)
            if new_content_length < min_acceptable_length and existing_content_length > 100:
                return {
                    "success": False,
                    "error": f"SAFETY BLOCK: Refusing to overwrite Shopify article with significantly shorter content. "
                             f"Existing: {existing_content_length} chars, New: {new_content_length} chars. "
                             f"New content must be at least 80% of existing length ({min_acceptable_length} chars). "
                             f"This protection prevents accidental data loss from bad imports.",
                }
    # ==========================================================================

    # Get publish settings based on status
    publish_settings = get_shopify_publish_settings(status, scheduled_at)

    # Build article input
    article_input = {
        "title": title,
        "handle": slug,
        "body": body_html,
        "isPublished": publish_settings.get("isPublished", False),
    }

    # Only include summary if we have a real excerpt (not empty/placeholder)
    # This preserves existing Shopify excerpts when Supabase has none
    if excerpt and excerpt.strip() and excerpt != "No excerpt available.":
        article_input["summary"] = excerpt

    # Add publishDate if present (for scheduled posts)
    if "publishDate" in publish_settings:
        article_input["publishDate"] = publish_settings["publishDate"]

    # Add author
    if author_name:
        article_input["author"] = {"name": author_name}
    elif SHOPIFY_DEFAULT_AUTHOR:
        article_input["author"] = {"name": SHOPIFY_DEFAULT_AUTHOR}

    # Add featured image
    # Skip Shopify CDN URLs - they're already hosted on Shopify, no need to re-upload
    # Re-uploading them causes "file not found" errors and can remove existing images
    if featured_image and "cdn.shopify.com" not in featured_image:
        article_input["image"] = {
            "url": featured_image,
            "altText": featured_image_alt or f"Featured image for {title}",
        }
    elif featured_image and "cdn.shopify.com" in featured_image:
        # Image is already on Shopify - don't include in update to preserve existing
        pass

    # Add tags
    if tags:
        article_input["tags"] = tags

    # Build metafields from SEO data
    metafields = build_seo_metafields(seo)
    if metafields:
        article_input["metafields"] = metafields

    # If no existing ID provided, check if article already exists in Shopify
    if not existing_shopify_id:
        existing_shopify_id = await find_article_by_handle(shopify_blog_gid, slug)

    if existing_shopify_id:
        # Update existing article
        query = """
        mutation UpdateArticle($id: ID!, $article: ArticleUpdateInput!) {
            articleUpdate(id: $id, article: $article) {
                article { id title handle }
                userErrors { code field message }
            }
        }
        """
        variables = {
            "id": existing_shopify_id,
            "article": article_input,
        }

        result = await execute_shopify_graphql(query, variables)

        if "error" in result:
            # Check if this is a "not found" error - article may have been deleted
            error_lower = result["error"].lower()
            if "not found" in error_lower or "does not exist" in error_lower:
                # Fall back to checking by handle
                existing_shopify_id = await find_article_by_handle(shopify_blog_gid, slug)
                if existing_shopify_id:
                    # Retry update with correct ID
                    variables["id"] = existing_shopify_id
                    result = await execute_shopify_graphql(query, variables)
                else:
                    # Article truly doesn't exist, create it
                    existing_shopify_id = None
            else:
                return {"success": False, "error": result["error"]}

        if existing_shopify_id:  # Still updating
            update_result = result.get("articleUpdate", {})
            user_errors = update_result.get("userErrors", [])

            if user_errors:
                # Check for "not found" type errors
                error_codes = [e.get("code", "") for e in user_errors]
                if any(code in ("INVALID", "NOT_FOUND") for code in error_codes):
                    # Stale ID - check by handle and create if needed
                    existing_shopify_id = await find_article_by_handle(shopify_blog_gid, slug)
                    if not existing_shopify_id:
                        existing_shopify_id = None  # Will create below
                else:
                    error_msg = "; ".join([e.get("message", str(e)) for e in user_errors])
                    return {"success": False, "error": error_msg}
            else:
                article = update_result.get("article", {})
                if article:
                    # Cache the result
                    cache_key = f"{shopify_blog_gid}:{slug}"
                    _article_cache[cache_key] = article.get("id")
                    return {
                        "success": True,
                        "shopify_article_id": article.get("id"),
                        "handle": article.get("handle"),
                    }

    if not existing_shopify_id:
        # Create new article (only if it truly doesn't exist)
        article_input["blogId"] = shopify_blog_gid

        query = """
        mutation CreateArticle($article: ArticleCreateInput!) {
            articleCreate(article: $article) {
                article { id title handle }
                userErrors { code field message }
            }
        }
        """
        variables = {
            "article": article_input,
        }

        result = await execute_shopify_graphql(query, variables)

        if "error" in result:
            return {"success": False, "error": result["error"]}

        create_result = result.get("articleCreate", {})
        user_errors = create_result.get("userErrors", [])

        if user_errors:
            error_msg = "; ".join([e.get("message", str(e)) for e in user_errors])
            return {"success": False, "error": error_msg}

        article = create_result.get("article", {})
        # Cache the result
        cache_key = f"{shopify_blog_gid}:{slug}"
        _article_cache[cache_key] = article.get("id")
        return {
            "success": True,
            "shopify_article_id": article.get("id"),
            "handle": article.get("handle"),
        }
