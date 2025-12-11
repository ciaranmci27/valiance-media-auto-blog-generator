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
DEFAULT_AUTHOR_SLUG = os.getenv("DEFAULT_AUTHOR_SLUG", "clutchcaddie-team")
DEFAULT_STATUS = os.getenv("DEFAULT_STATUS", "draft")

# ===========================================
# Claude Configuration
# ===========================================
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
MAX_TURNS = int(os.getenv("MAX_TURNS", "15"))

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

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Please copy .env.example to .env and fill in your values."
        )

    return True
