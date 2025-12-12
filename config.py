"""
Configuration for ClutchCaddie Blog Generator
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ===========================================
# API Configuration
# ===========================================
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# ===========================================
# Blog Configuration
# ===========================================
DEFAULT_AUTHOR_SLUG = os.getenv("DEFAULT_AUTHOR_SLUG", "valiance-media")
DEFAULT_STATUS = os.getenv("DEFAULT_STATUS", "draft")

# ===========================================
# Category Configuration
# ===========================================
# Whether Claude can create new categories (default: false - use existing only)
ALLOW_NEW_CATEGORIES = os.getenv("ALLOW_NEW_CATEGORIES", "false").lower() == "true"

# Fallback category if no existing category fits (must exist in database)
DEFAULT_CATEGORY_SLUG = os.getenv("DEFAULT_CATEGORY_SLUG", "general")

# ===========================================
# Claude Configuration
# ===========================================
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
MAX_TURNS = int(os.getenv("MAX_TURNS", "15"))
BLOGS_PER_RUN = int(os.getenv("BLOGS_PER_RUN", "1"))

# ===========================================
# Image Generation Configuration (Nano Banana / Gemini)
# ===========================================
ENABLE_IMAGE_GENERATION = os.getenv("ENABLE_IMAGE_GENERATION", "false").lower() == "true"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-pro-image")
IMAGE_ASPECT_RATIO = os.getenv("IMAGE_ASPECT_RATIO", "21:9")
IMAGE_RESOLUTION = os.getenv("IMAGE_RESOLUTION", "2K")
IMAGE_QUALITY = int(os.getenv("IMAGE_QUALITY", "85"))
IMAGE_WIDTH = int(os.getenv("IMAGE_WIDTH", "1600"))
SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "blog-images")

# Context/theme for generated images (e.g., "golf course, outdoor sports, sunny day")
IMAGE_CONTEXT = os.getenv("IMAGE_CONTEXT", "")

# Style prefix for realistic photography - prepended to all image prompts
# Includes "no text" instruction to prevent Gemini from rendering text in images
IMAGE_STYLE_PREFIX = os.getenv(
    "IMAGE_STYLE_PREFIX",
    "Professional photograph, ultra realistic, high quality DSLR photography, "
    "natural lighting, sharp focus, detailed textures, "
    "no text, no words, no letters, no watermarks, no logos, no typography, "
)

# ===========================================
# Content Block Types (for reference)
# ===========================================
SUPPORTED_BLOCK_TYPES = [
    "paragraph",
    "heading",
    "quote",
    "list",
    "checklist",
    "proscons",
    "image",
    "gallery",
    "video",
    "embed",
    "table",
    "stats",
    "accordion",
    "button",
    "tableOfContents",
    "code",
    "callout",
    "divider",
]

# ===========================================
# Supabase Headers Helper
# ===========================================
def get_supabase_headers():
    """Get headers for Supabase REST API calls"""
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


# ===========================================
# Validation
# ===========================================
def validate_config():
    """Validate required configuration is present"""
    missing = []

    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_KEY:
        missing.append("SUPABASE_SERVICE_KEY")
    
    # Validate image generation config if enabled
    if ENABLE_IMAGE_GENERATION and not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY (required when ENABLE_IMAGE_GENERATION=true)")

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Please copy .env.example to .env and fill in your values."
        )

    return True
