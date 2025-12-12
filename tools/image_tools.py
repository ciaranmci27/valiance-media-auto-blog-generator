"""
Image Generation Tools - Generate featured images using Nano Banana (Gemini)

These tools allow Claude to generate high-quality featured images for blog posts
using Google's Gemini image generation models.
"""

import base64
import io
import json
from typing import Any
import aiohttp
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    ENABLE_IMAGE_GENERATION,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    IMAGE_ASPECT_RATIO,
    IMAGE_RESOLUTION,
    IMAGE_QUALITY,
    IMAGE_WIDTH,
    IMAGE_STYLE_PREFIX,
    IMAGE_CONTEXT,
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY,
    SUPABASE_STORAGE_BUCKET,
)

# Aspect ratio to height calculation
ASPECT_RATIOS = {
    "1:1": 1.0,
    "2:3": 2/3,
    "3:2": 3/2,
    "3:4": 3/4,
    "4:3": 4/3,
    "4:5": 4/5,
    "5:4": 5/4,
    "9:16": 9/16,
    "16:9": 16/9,
    "21:9": 21/9,
}


def calculate_dimensions(width: int, aspect_ratio: str) -> tuple[int, int]:
    """Calculate height from width and aspect ratio."""
    ratio = ASPECT_RATIOS.get(aspect_ratio, 21/9)
    height = int(width / ratio)
    return width, height


async def generate_featured_image(args: dict[str, Any]) -> dict[str, Any]:
    """
    Generate a featured image using Nano Banana (Gemini) and upload to Supabase.

    Args:
        prompt: Description of the image to generate (will be enhanced with style prefix)
        category_slug: The blog category slug - used as the folder name
        post_slug: The blog post slug - used as the filename

    Returns:
        The public URL of the uploaded image in format: bucket/{category_slug}/{post_slug}.webp
    """
    # Check if image generation is enabled - soft skip if disabled
    if not ENABLE_IMAGE_GENERATION:
        return {
            "content": [{
                "type": "text",
                "text": "SKIPPED: Image generation disabled. Continue without featured image."
            }]
        }

    if not GEMINI_API_KEY:
        return {
            "content": [{
                "type": "text",
                "text": "SKIPPED: GEMINI_API_KEY not configured. Continue without featured image."
            }]
        }

    prompt = args.get("prompt")
    if not prompt:
        return {
            "content": [{"type": "text", "text": "Missing required parameter: prompt"}],
            "is_error": True
        }

    category_slug = args.get("category_slug", "")
    post_slug = args.get("post_slug", "")
    
    if not category_slug:
        return {
            "content": [{"type": "text", "text": "Missing required parameter: category_slug (the category folder name)"}],
            "is_error": True
        }
    
    if not post_slug:
        return {
            "content": [{"type": "text", "text": "Missing required parameter: post_slug (the image filename)"}],
            "is_error": True
        }

    try:
        # Step 1: Generate image with Gemini API
        # Build prompt: style prefix + context (if set) + user prompt
        context_part = f"Setting: {IMAGE_CONTEXT}. " if IMAGE_CONTEXT else ""
        full_prompt = f"{IMAGE_STYLE_PREFIX}{context_part}{prompt}"

        # Set timeout for API calls (60s for image generation, 30s for upload)
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Call Gemini API
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": GEMINI_API_KEY,
            }

            payload = {
                "contents": [{
                    "parts": [{"text": full_prompt}]
                }],
                "generationConfig": {
                    "responseModalities": ["TEXT", "IMAGE"],
                }
            }

            async with session.post(gemini_url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    # Graceful degradation - don't block blog creation
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"SKIPPED: Gemini API error ({resp.status}). Continue without featured image."
                        }]
                    }

                result = await resp.json()

            # Extract base64 image from response
            image_data = None
            mime_type = "image/png"

            try:
                for part in result["candidates"][0]["content"]["parts"]:
                    if "inlineData" in part:
                        image_data = part["inlineData"]["data"]
                        mime_type = part["inlineData"].get("mimeType", "image/png")
                        break
            except (KeyError, IndexError):
                # Graceful degradation
                return {
                    "content": [{
                        "type": "text",
                        "text": "SKIPPED: Could not extract image from response. Continue without featured image."
                    }]
                }

            if not image_data:
                return {
                    "content": [{
                        "type": "text",
                        "text": "SKIPPED: No image in response (model may have refused). Continue without featured image."
                    }]
                }

            # Step 2: Process image with Pillow
            try:
                from PIL import Image, ImageFilter

                # Decode base64 image
                image_bytes = base64.b64decode(image_data)
                image = Image.open(io.BytesIO(image_bytes))

                # Calculate target dimensions
                target_width, target_height = calculate_dimensions(IMAGE_WIDTH, IMAGE_ASPECT_RATIO)

                # Resize image maintaining aspect ratio, then crop to exact dimensions
                # First, scale to cover the target area
                img_ratio = image.width / image.height
                target_ratio = target_width / target_height

                if img_ratio > target_ratio:
                    # Image is wider, scale by height
                    new_height = target_height
                    new_width = int(target_height * img_ratio)
                else:
                    # Image is taller, scale by width
                    new_width = target_width
                    new_height = int(target_width / img_ratio)

                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Center crop to exact dimensions
                left = (new_width - target_width) // 2
                top = (new_height - target_height) // 2
                right = left + target_width
                bottom = top + target_height
                image = image.crop((left, top, right, bottom))

                # Apply light sharpening to restore detail lost during resize
                # UnsharpMask(radius, percent, threshold) - subtle settings for natural look
                image = image.filter(ImageFilter.UnsharpMask(radius=1.0, percent=50, threshold=2))

                # Convert to RGB if necessary (for WebP)
                if image.mode in ('RGBA', 'P'):
                    # Create white background for transparency
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    if image.mode == 'P':
                        image = image.convert('RGBA')
                    background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                    image = background
                elif image.mode != 'RGB':
                    image = image.convert('RGB')

                # Adaptive quality WebP encoding
                # Start with configured quality, reduce only if file is too large
                # This prioritizes quality while keeping files reasonable
                MAX_FILE_SIZE_KB = 500  # Target max size in KB
                MIN_QUALITY = 75  # Never go below this for quality

                final_quality = IMAGE_QUALITY
                webp_data = None

                for quality in [IMAGE_QUALITY, 85, 80, MIN_QUALITY]:
                    if quality > IMAGE_QUALITY:
                        continue  # Don't go higher than configured

                    output_buffer = io.BytesIO()
                    # method=6 is slowest but best compression
                    # exact=True preserves RGB values more accurately
                    image.save(
                        output_buffer,
                        format='WEBP',
                        quality=quality,
                        method=6,
                    )
                    webp_data = output_buffer.getvalue()
                    final_quality = quality

                    file_size_kb = len(webp_data) / 1024

                    # If under max size or at minimum quality, we're done
                    if file_size_kb <= MAX_FILE_SIZE_KB or quality == MIN_QUALITY:
                        break

            except ImportError:
                return {
                    "content": [{
                        "type": "text",
                        "text": "SKIPPED: Pillow not installed. Continue without featured image."
                    }]
                }
            except Exception as e:
                # Graceful degradation for processing errors
                return {
                    "content": [{
                        "type": "text",
                        "text": f"SKIPPED: Image processing failed. Continue without featured image."
                    }]
                }

            # Step 3: Upload to Supabase Storage organized by category folder
            # Sanitize slugs for path
            safe_category = "".join(c if c.isalnum() or c in '-_' else '-' for c in category_slug)[:50]
            safe_post = "".join(c if c.isalnum() or c in '-_' else '-' for c in post_slug)[:100]
            
            # Create path: bucket/category/post.webp (e.g., blog-images/golf-tips/best-golf-drivers-2025.webp)
            file_path = f"{safe_category}/{safe_post}.webp"
            
            storage_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_STORAGE_BUCKET}/{file_path}"

            upload_headers = {
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "image/webp",
                "x-upsert": "true",
            }

            async with session.post(storage_url, headers=upload_headers, data=webp_data) as resp:
                if resp.status not in [200, 201]:
                    # Graceful degradation - image generated but upload failed
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"SKIPPED: Storage upload failed ({resp.status}). Continue without featured image."
                        }]
                    }

            # Generate public URL
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_STORAGE_BUCKET}/{file_path}"

            # Calculate file size
            file_size_kb = len(webp_data) / 1024

            # Note if quality was adjusted
            quality_note = ""
            if final_quality < IMAGE_QUALITY:
                quality_note = f" (reduced from {IMAGE_QUALITY}% to meet size target)"

            return {
                "content": [{
                    "type": "text",
                    "text": f"""Featured image generated successfully!

URL: {public_url}
Path: {SUPABASE_STORAGE_BUCKET}/{file_path}
Dimensions: {target_width}x{target_height}
Format: WebP (optimized)
Quality: {final_quality}%{quality_note}
File size: {file_size_kb:.1f} KB

Use this URL as the featured_image when creating the blog post."""
                }]
            }

    except Exception as e:
        # Graceful degradation for any unexpected errors
        return {
            "content": [{
                "type": "text",
                "text": f"SKIPPED: Unexpected error. Continue without featured image."
            }]
        }


# Tool definitions for Claude Agent SDK
IMAGE_TOOLS = [
    {
        "name": "generate_featured_image",
        "description": "Generate featured image via AI. Returns SKIPPED if fails (graceful). Stored at blog-images/{category_slug}/{post_slug}.webp",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Image description (scene, lighting, composition)"},
                "category_slug": {"type": "string", "description": "Category slug for folder"},
                "post_slug": {"type": "string", "description": "Post slug for filename"}
            },
            "required": ["prompt", "category_slug", "post_slug"]
        },
        "function": generate_featured_image
    }
]
