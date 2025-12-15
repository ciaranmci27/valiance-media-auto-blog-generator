"""
Link Tools - Internal linking suggestions and URL validation

These tools help Claude build high-quality internal and external links
following SEO best practices (3-5 internal links per 1,000 words).
"""

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
import aiohttp
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SUPABASE_URL,
    get_supabase_headers,
    INTERNAL_LINK_PATTERN,
    LINK_VALIDATION_TIMEOUT,
    LINK_SUGGESTIONS_LIMIT,
    ANTHROPIC_API_KEY,
)


def build_internal_url(slug: str, category_slug: str = None) -> str:
    """Build internal URL from configured pattern."""
    url = INTERNAL_LINK_PATTERN.replace("{slug}", slug)
    if "{category}" in url:
        if category_slug:
            url = url.replace("{category}", category_slug)
        else:
            # Remove category placeholder if not available
            url = url.replace("{category}/", "").replace("{category}", "")
    return url


def extract_slug_from_internal_url(url: str) -> str | None:
    """Extract post slug from internal URL based on pattern."""
    # Build regex from pattern: /blog/{slug} -> /blog/([^/]+)
    pattern = INTERNAL_LINK_PATTERN
    regex_pattern = pattern.replace("{category}", "[^/]+").replace("{slug}", "([^/]+)")
    regex_pattern = f"^{regex_pattern}$"

    match = re.match(regex_pattern, url)
    if match:
        return match.group(1)

    # Fallback: try to get last path segment
    parts = url.strip("/").split("/")
    return parts[-1] if parts else None


def is_internal_url(url: str) -> bool:
    """Check if URL is internal (relative path, not http/https)."""
    return url.startswith("/") and not url.startswith("//")


def extract_domain(url: str) -> str | None:
    """Extract domain from external URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return domain if domain else None
    except Exception:
        return None


def extract_anchor_patterns(title: str) -> list[str]:
    """
    Extract meaningful phrases from a post title that would work as anchor text.
    Returns phrases that Claude should search for in the content.

    Example: "How to Fix Your Slice - Complete Guide"
    Returns: ["fix your slice", "slice", "fixing your slice"]
    """
    # Common filler words to remove
    stop_words = {
        'a', 'an', 'the', 'how', 'to', 'what', 'is', 'are', 'was', 'were',
        'for', 'of', 'in', 'on', 'at', 'by', 'with', 'your', 'my', 'our',
        'this', 'that', 'these', 'those', 'and', 'or', 'but', 'so',
        'complete', 'guide', 'ultimate', 'best', 'top', 'tips', 'tricks',
        'beginners', 'beginner', 'advanced', 'simple', 'easy', 'quick'
    }

    # Clean title: remove punctuation, lowercase
    clean_title = re.sub(r'[^\w\s]', ' ', title.lower())
    words = clean_title.split()

    # Filter out stop words for core concepts
    core_words = [w for w in words if w not in stop_words and len(w) > 2]

    patterns = []

    # 1. Full meaningful phrase (2-4 content words)
    if len(core_words) >= 2:
        # Take first 2-3 core words as a phrase
        phrase = ' '.join(core_words[:3])
        if len(phrase) > 5:
            patterns.append(phrase)

    # 2. Key bigrams from core words
    for i in range(len(core_words) - 1):
        bigram = f"{core_words[i]} {core_words[i+1]}"
        if bigram not in patterns and len(bigram) > 5:
            patterns.append(bigram)

    # 3. Single important words (nouns likely)
    for word in core_words:
        if len(word) > 4 and word not in patterns:
            patterns.append(word)

    # Limit to top 5 patterns
    return patterns[:5]


def is_quality_anchor(anchor: str) -> bool:
    """
    Validate that an anchor text is specific enough to be a quality link.
    Rejects overly generic, single-word, or vague anchors.

    Returns True if anchor passes quality checks, False otherwise.
    """
    if not anchor:
        return False

    anchor_lower = anchor.lower().strip()
    words = anchor_lower.split()

    # Reject single words (too generic)
    if len(words) < 2:
        return False

    # Reject very short anchors (less than 8 chars total)
    if len(anchor_lower) < 8:
        return False

    # Generic terms that are too vague on their own
    generic_terms = {
        # Single concept generics
        'golf tips', 'golf rules', 'golf equipment', 'golf courses',
        'golf clubs', 'golf balls', 'golf game', 'golf swing',
        'the masters', 'the open', 'the pga', 'pga tour',
        'ball striking', 'club head', 'swing speed',
        # Overly broad phrases
        'how to golf', 'golf basics', 'golf guide', 'golf help',
        'learn golf', 'play golf', 'playing golf',
        # Generic instructional
        'tips and tricks', 'best practices', 'common mistakes',
        'quick tips', 'easy tips', 'simple tips',
    }

    if anchor_lower in generic_terms:
        return False

    # Check if it's just a proper noun (capitalized words only)
    # This catches "The Masters", "Tiger Woods", etc.
    original_words = anchor.strip().split()
    if all(w[0].isupper() for w in original_words if w):
        # All words are capitalized - likely a proper noun
        # Only allow if it's descriptive (3+ words)
        if len(original_words) < 3:
            return False

    return True


def filter_quality_anchors(anchors: list[str]) -> list[str]:
    """Filter anchor patterns to only include quality anchors."""
    return [a for a in anchors if is_quality_anchor(a)]


async def score_link_relevance(
    source_title: str,
    source_excerpt: str,
    candidates: list[dict],
) -> list[dict]:
    """
    Use Claude Haiku to score relevance AND extract semantic anchor patterns.
    Returns only candidates with relevance score >= 8, with AI-generated patterns.

    This prevents:
    - Irrelevant links (e.g., "slice fix" article linking to "bag rules" article)
    - Bad anchor text (e.g., "golf ball" linking to "how to stop topping")
    - Semantic mismatches (e.g., "grip" meaning traction vs technique)

    The anchor patterns are semantically meaningful - they describe what the
    TARGET article is actually about, not just words from the title.

    Args:
        source_title: Title of the post being enhanced
        source_excerpt: Brief description of the source post
        candidates: List of potential link targets with title and url

    Returns:
        Filtered list of relevant candidates, each with:
        - relevance_score: 7-10 rating
        - anchor_patterns: Phrases to search for in content
        - anti_patterns: Phrases to AVOID (different semantic meaning)
        - semantic_intent: What the target article teaches
    """
    if not candidates:
        return []

    # Build the scoring prompt - batch all candidates in one call
    candidate_list = "\n".join([
        f"{i+1}. \"{c['title']}\""
        for i, c in enumerate(candidates)
    ])

    prompt = f"""You are a STRICT evaluator of internal links. Your job is to REJECT weak links.

SOURCE ARTICLE: "{source_title}"
{f'Description: {source_excerpt}' if source_excerpt else ''}

CANDIDATE LINKS (potential pages to link TO):
{candidate_list}

For EACH candidate, provide:
1. score (1-10): STRICT scoring - see criteria below
2. anchors: 2-4 SPECIFIC phrases (not generic terms)
3. anti: phrases that look similar but have DIFFERENT meaning
4. intent: 5-10 word description of target's core concept

STRICT SCORING CRITERIA:
- 9-10: DIRECTLY answers a question the source reader would have
        Example: "Golf Cart Costs" → "Golf Cart Maintenance Costs" ✓
- 7-8: Closely related sub-topic that provides genuine value
        Example: "Golf Cart Costs" → "Electric vs Gas Golf Carts" ✓
- 4-6: Same broad category but DIFFERENT focus - DO NOT LINK
        Example: "Golf Cart Costs" → "How Many Golf Courses in USA" ✗
- 1-3: Unrelated - just happens to be in same niche

CRITICAL - SCORE LOW (1-5) IF:
- Topics share a category but have DIFFERENT purposes
- Link would only make sense because they're "both about [niche]"
- Reader would think "why is this linked here?"
- Anchor would be a generic term (single words, proper nouns alone)

BAD LINK EXAMPLES (score 1-5):
- "Golf Cart Costs" → "How Many Clubs Allowed in Bag" (DIFFERENT topics, score: 2)
- "Golf Cart Costs" → "How Many Golf Courses in USA" (DIFFERENT topics, score: 2)
- "History of Golf" → "When is The Masters 2025" (historical vs schedule, score: 3)
- "Inconsistent Ball Striking" → "Stop Topping the Ball" (broad vs specific, score: 5)

GOOD LINK EXAMPLES (score 8-10):
- "Golf Cart Costs" → "Golf Cart Maintenance Guide" (same topic area, score: 9)
- "How to Grip a Golf Club" → "Common Grip Mistakes" (complementary, score: 9)
- "Best Drivers 2025" → "Driver Fitting Guide" (helps same reader, score: 8)

ANCHOR QUALITY RULES (CRITICAL):
- NEVER use single generic words: "golf", "course", "club", "driver"
- NEVER use proper nouns alone: "The Masters", "PGA", "Tiger Woods"
- NEVER use vague phrases: "golf equipment", "golf rules", "golf tips"
- ALWAYS use specific, descriptive phrases that explain what reader will learn
- Anchors must be 2-5 words and describe the TARGET's specific value

BAD ANCHORS: ["Golf courses", "The Masters", "golf equipment rules", "ball striking"]
GOOD ANCHORS: ["golf cart maintenance costs", "grip pressure mistakes", "driver loft selection"]

SEMANTIC DISAMBIGUATION:
Same word can have different meanings - generate anti-patterns to avoid wrong contexts.

Respond with ONLY a JSON array:
[{{"score": 8, "anchors": ["specific phrase 1", "specific phrase 2"], "anti": ["avoid1"], "intent": "core concept"}}, {{"score": 2, "anchors": [], "anti": [], "intent": ""}}]"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-5-haiku-20241022",
                    "max_tokens": 800,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    # On error, fall back to regex patterns (no anti-patterns available)
                    for c in candidates:
                        c["anchor_patterns"] = extract_anchor_patterns(c["title"])
                        c["anti_patterns"] = []
                        c["semantic_intent"] = ""
                    return candidates

                result = await resp.json()
                response_text = result.get("content", [{}])[0].get("text", "")

                # Parse the JSON array
                response_text = response_text.strip()
                if response_text.startswith("```"):
                    response_text = response_text.split("\n", 1)[-1].rsplit("```", 1)[0]

                evaluations = json.loads(response_text)

                if not isinstance(evaluations, list) or len(evaluations) != len(candidates):
                    # Invalid response, fall back (no anti-patterns available)
                    for c in candidates:
                        c["anchor_patterns"] = extract_anchor_patterns(c["title"])
                        c["anti_patterns"] = []
                        c["semantic_intent"] = ""
                    return candidates

                # Filter to relevant candidates and add AI-generated patterns
                relevant = []
                for candidate, evaluation in zip(candidates, evaluations):
                    score = evaluation.get("score", 0)
                    anchors = evaluation.get("anchors", [])
                    anti_patterns = evaluation.get("anti", [])
                    semantic_intent = evaluation.get("intent", "")

                    if isinstance(score, (int, float)) and score >= 8:
                        # Filter anchors to only quality ones
                        quality_anchors = filter_quality_anchors(anchors)

                        # Fall back to extracted patterns if no quality anchors
                        if not quality_anchors:
                            quality_anchors = filter_quality_anchors(extract_anchor_patterns(candidate["title"]))

                        # Skip candidate entirely if no quality anchors available
                        if not quality_anchors:
                            continue

                        candidate["relevance_score"] = score
                        candidate["anchor_patterns"] = quality_anchors
                        candidate["anti_patterns"] = anti_patterns if anti_patterns else []
                        candidate["semantic_intent"] = semantic_intent
                        relevant.append(candidate)

                return relevant

    except Exception as e:
        # On any error, fail open with regex patterns (no anti-patterns available)
        for c in candidates:
            c["anchor_patterns"] = extract_anchor_patterns(c["title"])
            c["anti_patterns"] = []
            c["semantic_intent"] = ""
        return candidates


def extract_sentence_context(text: str, anchor: str, context_chars: int = 150) -> str:
    """
    Extract the sentence or surrounding context containing the anchor text.
    Used for context-aware link validation.
    """
    anchor_lower = anchor.lower()
    text_lower = text.lower()

    pos = text_lower.find(anchor_lower)
    if pos == -1:
        return ""

    # Find sentence boundaries (., !, ?, or start/end of text)
    # Look backwards for sentence start
    start = pos
    for i in range(pos - 1, max(0, pos - context_chars), -1):
        if text[i] in '.!?\n':
            start = i + 1
            break
    else:
        start = max(0, pos - context_chars)

    # Look forwards for sentence end
    end = pos + len(anchor)
    for i in range(pos + len(anchor), min(len(text), pos + context_chars)):
        if text[i] in '.!?\n':
            end = i + 1
            break
    else:
        end = min(len(text), pos + context_chars)

    return text[start:end].strip()


async def validate_link_context(
    anchor_text: str,
    context: str,
    target_title: str,
) -> bool:
    """
    Use Haiku to verify that linking anchor_text in this context makes sense
    for the target article.

    This prevents linking words used in different semantic contexts, e.g.,
    "grip" (traction) should not link to an article about "grip" (technique).
    """
    if not context or not anchor_text or not target_title:
        return False

    prompt = f"""You are a STRICT link quality evaluator. REJECT weak or irrelevant links.

ANCHOR TEXT: "{anchor_text}"
CONTEXT: "{context}"
TARGET ARTICLE: "{target_title}"

Ask yourself:
1. Is the anchor SPECIFIC (not generic like "golf tips", "The Masters")?
2. Would a reader HERE genuinely want to click to that target?
3. Does the anchor ACCURATELY describe what the target teaches?

Say "no" if:
- Anchor is too generic or vague
- Target is only loosely related (same niche but different topic)
- Reader would think "why is this linked here?"

Examples (apply pattern to any niche):
- "Golf courses" → "How Many Golf Courses in USA" = NO (generic anchor, unrelated to reader's goal)
- "The Masters" → "When is Masters 2025" = NO (proper noun alone, doesn't help reader)
- "grip technique" → "How to Grip a Golf Club" = YES (specific, directly helpful)

Answer ONLY "yes" or "no".
- "yes" = specific anchor + genuinely helpful link
- "no" = generic, loosely related, or unhelpful"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-5-haiku-20241022",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    return True  # Fail open on API error

                result = await resp.json()
                response_text = result.get("content", [{}])[0].get("text", "").lower().strip()
                return response_text.startswith("yes")

    except Exception:
        return True  # Fail open on error


async def validate_link_contexts_batch(
    insertions: list[dict],
    content_blocks: list[dict],
) -> list[dict]:
    """
    Batch validate multiple link insertions for context appropriateness.
    Returns only insertions that pass context validation.
    """
    if not insertions:
        return []

    # First, find all contexts
    contexts = []
    for insertion in insertions:
        anchor = insertion.get("anchor_text", "")
        target_title = insertion.get("target_title", "")

        # Search all text blocks for context
        context = ""
        for block in content_blocks:
            block_type = block.get("type", "")
            data = block.get("data", {})

            text = ""
            if block_type == "paragraph":
                text = data.get("text", "")
            elif block_type == "callout":
                text = data.get("text", "")
            elif block_type == "list":
                text = " ".join(data.get("items", []))

            if text and anchor.lower() in text.lower():
                context = extract_sentence_context(text, anchor)
                break

        contexts.append({
            "insertion": insertion,
            "context": context,
            "target_title": target_title
        })

    # Build batch prompt for efficiency
    validations = []
    for i, ctx in enumerate(contexts):
        if ctx["context"]:
            validations.append(f'{i+1}. Anchor: "{ctx["insertion"]["anchor_text"]}" | Context: "{ctx["context"][:100]}..." | Target: "{ctx["target_title"]}"')

    if not validations:
        return insertions  # No contexts found, return all

    prompt = f"""You are a STRICT link quality evaluator. REJECT weak or irrelevant links.

{chr(10).join(validations)}

For EACH link, ask these questions:
1. Does the anchor text ACCURATELY describe what the target teaches?
2. Would a reader AT THIS POINT genuinely want to click this link?
3. Is this link HELPFUL or just "related to the same topic"?

REJECT (false) if ANY of these are true:
- Anchor is too GENERIC (e.g., "Golf courses", "The Masters", "golf tips")
- Target article is only LOOSELY related (same niche but different topic)
- Reader would think "why is this linked here?"
- Anchor doesn't clearly describe what they'll learn by clicking

These examples illustrate the pattern - apply to ANY niche:

REJECT EXAMPLES (answer: false):
- Anchor "Golf courses" | Context: "...cost varies by golf courses..." | Target: "How Many Golf Courses in USA"
  → Generic anchor, reader doesn't want statistics while reading about costs → false

- Anchor "The Masters" | Context: "...history of The Masters tournament..." | Target: "When is The Masters 2025"
  → Historical context, schedule article doesn't fit → false

- Anchor "golf equipment rules" | Context: "...follow golf equipment rules..." | Target: "How Many Clubs Allowed in Bag"
  → Too vague anchor for specific rules article → false

- Anchor "ball striking" | Context: "...improve ball striking consistency..." | Target: "How to Stop Topping the Ball"
  → Broad concept linked to ONE specific type → false

APPROVE EXAMPLES (answer: true):
- Anchor "grip technique" | Context: "...proper grip technique matters for..." | Target: "How to Grip a Golf Club"
  → Specific anchor, directly relevant target → true

- Anchor "driver distance tips" | Context: "...maximize your driver distance tips..." | Target: "How to Hit Driver Farther"
  → Specific anchor matching target's purpose → true

- Anchor "common grip mistakes" | Context: "...avoid common grip mistakes..." | Target: "Golf Grip Mistakes to Avoid"
  → Perfect match between anchor and target → true

Answer with ONLY a JSON array of booleans: [true, false, true]
- true = specific anchor + genuinely helpful link
- false = generic anchor, loosely related, or reader wouldn't benefit"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-5-haiku-20241022",
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    return insertions  # Fail open

                result = await resp.json()
                response_text = result.get("content", [{}])[0].get("text", "").strip()

                # Parse JSON array
                if response_text.startswith("```"):
                    response_text = response_text.split("\n", 1)[-1].rsplit("```", 1)[0]

                validations_result = json.loads(response_text)

                if not isinstance(validations_result, list):
                    return insertions

                # Filter to only valid insertions
                valid_insertions = []
                validation_idx = 0
                for ctx in contexts:
                    if ctx["context"]:
                        if validation_idx < len(validations_result) and validations_result[validation_idx]:
                            valid_insertions.append(ctx["insertion"])
                        validation_idx += 1
                    else:
                        # No context found, include anyway
                        valid_insertions.append(ctx["insertion"])

                return valid_insertions

    except Exception:
        return insertions  # Fail open


async def get_internal_link_suggestions(args: dict[str, Any]) -> dict[str, Any]:
    """
    Find related posts for internal linking based on topic keywords.
    Uses LLM-based relevance scoring to filter out unrelated suggestions.
    Returns compact list with pre-built URLs for direct use in anchor tags.
    Returns clear guidance when catalog is too small for quality linking.
    """
    try:
        topic = args.get("topic", "").strip()  # Usually the source post title
        source_excerpt = args.get("source_excerpt", "")  # Optional description
        category_id = args.get("category_id")
        exclude_slug = args.get("exclude_slug")
        limit = min(args.get("limit", LINK_SUGGESTIONS_LIMIT), 15)

        if not topic:
            return {"content": [{"type": "text", "text": "Error: topic required"}], "is_error": True}

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # First, check total published post count to assess catalog size
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?select=id&status=eq.published",
                headers={**headers, "Prefer": "count=exact"}
            ) as resp:
                # Get count from content-range header
                content_range = resp.headers.get("content-range", "")
                total_posts = 0
                if "/" in content_range:
                    try:
                        total_posts = int(content_range.split("/")[1])
                    except (ValueError, IndexError):
                        pass

            # If catalog is very small, skip internal linking
            if total_posts < 3:
                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "skip_internal_links": True,
                            "reason": f"Catalog too small ({total_posts} posts). Skip internal linking for now.",
                            "suggestions": []
                        }, separators=(',', ':'))
                    }]
                }

            # Build query for published posts with category info
            select = "slug,title,excerpt,blog_categories(slug)"
            base_url = f"{SUPABASE_URL}/rest/v1/blog_posts?select={select}&status=eq.published"

            # Exclude current post if specified
            if exclude_slug:
                base_url += f"&slug=neq.{exclude_slug}"

            # Strategy 1: Same category posts (if category_id provided)
            same_category_posts = []
            if category_id:
                async with session.get(
                    f"{base_url}&category_id=eq.{category_id}&order=created_at.desc&limit={limit}",
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        same_category_posts = await resp.json()

            # Strategy 2: Search by topic keywords in title
            # Use ilike for case-insensitive partial match on first keyword
            keywords = topic.lower().split()[:3]  # First 3 words
            title_matches = []

            if keywords:
                # Search for posts with any keyword in title
                keyword = keywords[0]  # Primary keyword
                async with session.get(
                    f"{base_url}&title=ilike.*{keyword}*&order=created_at.desc&limit={limit}",
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        title_matches = await resp.json()

            # Combine and deduplicate results
            seen_slugs = set()
            combined = []

            # Add same category first (higher relevance)
            for post in same_category_posts:
                if post["slug"] not in seen_slugs:
                    seen_slugs.add(post["slug"])
                    combined.append(post)

            # Then title matches
            for post in title_matches:
                if post["slug"] not in seen_slugs:
                    seen_slugs.add(post["slug"])
                    combined.append(post)

            # Limit results before scoring (to control API costs)
            combined = combined[:limit]

            # Score candidates for semantic relevance using Haiku
            # This also generates AI-powered anchor patterns (not just regex extraction)
            scored_candidates = []
            if combined:
                # Prepare candidates for scoring
                scoring_candidates = [{"title": p["title"], "slug": p["slug"]} for p in combined]
                scored_candidates = await score_link_relevance(
                    source_title=topic,
                    source_excerpt=source_excerpt,
                    candidates=scoring_candidates
                )

            # If no relevant suggestions found, provide clear guidance
            if not scored_candidates:
                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "skip_internal_links": True,
                            "reason": f"No semantically relevant posts found for '{topic}'.",
                            "total_posts": total_posts,
                            "suggestions": []
                        }, separators=(',', ':'))
                    }]
                }

            # Build slug->scored_candidate map for anchor patterns
            slug_to_scored = {c["slug"]: c for c in scored_candidates}

            # Log relevance filtering results
            filtered_count = len(combined) - len(scored_candidates)
            if filtered_count > 0:
                print(f"  → Relevance filter: {len(combined)} candidates → {len(scored_candidates)} relevant (filtered {filtered_count} unrelated)")

            # Format output with pre-built URLs AND AI-generated anchor patterns
            suggestions = []
            for post in combined:
                if post["slug"] not in slug_to_scored:
                    continue  # Filtered out by relevance scoring

                scored = slug_to_scored[post["slug"]]
                cat_slug = None
                if post.get("blog_categories"):
                    cat_slug = post["blog_categories"].get("slug")

                suggestion = {
                    "url": build_internal_url(post["slug"], cat_slug),
                    "title": post["title"],
                    "anchor_patterns": scored.get("anchor_patterns", []),  # AI-generated patterns
                    "relevance_score": scored.get("relevance_score", 7)
                }
                # Include anti-patterns if available (for semantic disambiguation)
                if scored.get("anti_patterns"):
                    suggestion["anti_patterns"] = scored["anti_patterns"]
                if scored.get("semantic_intent"):
                    suggestion["semantic_intent"] = scored["semantic_intent"]
                suggestions.append(suggestion)

            # Log suggestions
            if suggestions:
                print(f"  → Found {len(suggestions)} relevant link targets:")
                for s in suggestions[:5]:  # Show first 5
                    patterns_preview = ", ".join(s["anchor_patterns"][:3]) if s["anchor_patterns"] else "none"
                    anti_preview = f" | avoid: {', '.join(s.get('anti_patterns', [])[:2])}" if s.get("anti_patterns") else ""
                    print(f"     • {s['title'][:40]}... (patterns: {patterns_preview}{anti_preview})")

            # Provide context-aware guidance based on catalog size
            # Must align with get_posts_needing_links caps
            if total_posts < 5:
                max_links = 1
                guidance = f"Very small catalog ({total_posts} posts). Use max 1 internal link."
            elif total_posts < 15:
                max_links = 2
                guidance = f"Small catalog ({total_posts} posts). Use max 2 internal links."
            elif total_posts < 30:
                max_links = 3
                guidance = f"Growing catalog ({total_posts} posts). Use max 3 internal links."
            elif total_posts < 50:
                max_links = 4
                guidance = f"Medium catalog ({total_posts} posts). Use max 4 internal links."
            else:
                max_links = None  # Full linking as per normal guidelines
                guidance = None

            response = {"suggestions": suggestions}
            if guidance:
                response["guidance"] = guidance
            if max_links:
                response["max_internal_links"] = max_links

            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps(response, separators=(',', ':'))
                }]
            }

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


async def validate_single_url(url: str, session: aiohttp.ClientSession, headers: dict) -> dict:
    """Validate a single URL (internal or external)."""
    timeout_sec = LINK_VALIDATION_TIMEOUT / 1000

    if is_internal_url(url):
        # Internal URL: validate against database
        slug = extract_slug_from_internal_url(url)
        if not slug:
            return {"url": url, "valid": False, "status": 400, "error": "Invalid URL format"}

        try:
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?slug=eq.{slug}&status=eq.published&select=slug",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout_sec)
            ) as resp:
                if resp.status == 200:
                    posts = await resp.json()
                    if posts:
                        return {"url": url, "valid": True, "status": 200}
                    return {"url": url, "valid": False, "status": 404, "error": "Post not found"}
                return {"url": url, "valid": False, "status": resp.status, "error": "DB error"}
        except asyncio.TimeoutError:
            return {"url": url, "valid": False, "status": 0, "error": "Timeout"}
        except Exception as e:
            return {"url": url, "valid": False, "status": 0, "error": str(e)[:50]}

    else:
        # External URL: HTTP HEAD request
        try:
            async with session.head(
                url,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=timeout_sec),
                headers={"User-Agent": "Mozilla/5.0 (compatible; BlogLinkValidator/1.0)"}
            ) as resp:
                result = {"url": url, "valid": resp.status < 400, "status": resp.status}

                # Track redirect if URL changed
                if str(resp.url) != url:
                    result["redirect"] = str(resp.url)

                if resp.status >= 400:
                    result["error"] = f"HTTP {resp.status}"

                return result

        except asyncio.TimeoutError:
            return {"url": url, "valid": False, "status": 0, "error": "Timeout"}
        except aiohttp.ClientError as e:
            return {"url": url, "valid": False, "status": 0, "error": str(type(e).__name__)}
        except Exception as e:
            return {"url": url, "valid": False, "status": 0, "error": str(e)[:50]}


async def validate_urls(args: dict[str, Any]) -> dict[str, Any]:
    """
    Validate multiple URLs in parallel.
    Internal URLs checked against database, external via HTTP HEAD.
    """
    try:
        urls = args.get("urls", [])

        if not urls:
            return {"content": [{"type": "text", "text": "[]"}]}

        # Deduplicate while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # Validate all URLs in parallel
            tasks = [validate_single_url(url, session, headers) for url in unique_urls]
            results = await asyncio.gather(*tasks)

        # Compact output format
        output = []
        for r in results:
            item = {"url": r["url"], "valid": r["valid"]}
            if not r["valid"]:
                item["error"] = r.get("error", f"HTTP {r.get('status', 0)}")
            if r.get("redirect"):
                item["redirect"] = r["redirect"]
            output.append(item)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(output, separators=(',', ':'))
            }]
        }

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


# =============================================================================
# Link Extraction and Storage (used by write_tools.py)
# =============================================================================

def extract_links_from_content(content: list, post_id: str) -> list[dict]:
    """
    Extract all links from content blocks for storage in blog_post_links.
    Returns list of link records ready for database insertion.
    """
    links = []

    # Regex to find <a> tags with href
    anchor_pattern = re.compile(
        r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL
    )

    # Also check for target and rel attributes
    target_pattern = re.compile(r'target=["\']_blank["\']', re.IGNORECASE)
    nofollow_pattern = re.compile(r'rel=["\'][^"\']*nofollow[^"\']*["\']', re.IGNORECASE)

    for block in content:
        block_type = block.get("type", "")
        data = block.get("data", {})

        # Check paragraph text for inline links
        if block_type == "paragraph":
            text = data.get("text", "")
            for match in anchor_pattern.finditer(text):
                full_tag = match.group(0)
                url = match.group(1)
                anchor_text = re.sub(r'<[^>]+>', '', match.group(2)).strip()  # Strip inner HTML

                links.append({
                    "post_id": post_id,
                    "url": url,
                    "anchor_text": anchor_text[:255] if anchor_text else None,
                    "link_type": "internal" if is_internal_url(url) else "external",
                    "domain": extract_domain(url) if not is_internal_url(url) else None,
                    "opens_new_tab": bool(target_pattern.search(full_tag)),
                    "is_nofollow": bool(nofollow_pattern.search(full_tag)),
                })

        # Check list items
        elif block_type == "list":
            for item in data.get("items", []):
                if isinstance(item, str):
                    for match in anchor_pattern.finditer(item):
                        full_tag = match.group(0)
                        url = match.group(1)
                        anchor_text = re.sub(r'<[^>]+>', '', match.group(2)).strip()

                        links.append({
                            "post_id": post_id,
                            "url": url,
                            "anchor_text": anchor_text[:255] if anchor_text else None,
                            "link_type": "internal" if is_internal_url(url) else "external",
                            "domain": extract_domain(url) if not is_internal_url(url) else None,
                            "opens_new_tab": bool(target_pattern.search(full_tag)),
                            "is_nofollow": bool(nofollow_pattern.search(full_tag)),
                        })

        # Check button blocks
        elif block_type == "button":
            url = data.get("url", "")
            if url:
                links.append({
                    "post_id": post_id,
                    "url": url,
                    "anchor_text": data.get("text", "")[:255],
                    "link_type": "internal" if is_internal_url(url) else "external",
                    "domain": extract_domain(url) if not is_internal_url(url) else None,
                    "opens_new_tab": data.get("newTab", False),
                    "is_nofollow": False,
                })

        # Check callout blocks (may have inline links)
        elif block_type == "callout":
            text = data.get("text", "")
            for match in anchor_pattern.finditer(text):
                full_tag = match.group(0)
                url = match.group(1)
                anchor_text = re.sub(r'<[^>]+>', '', match.group(2)).strip()

                links.append({
                    "post_id": post_id,
                    "url": url,
                    "anchor_text": anchor_text[:255] if anchor_text else None,
                    "link_type": "internal" if is_internal_url(url) else "external",
                    "domain": extract_domain(url) if not is_internal_url(url) else None,
                    "opens_new_tab": bool(target_pattern.search(full_tag)),
                    "is_nofollow": bool(nofollow_pattern.search(full_tag)),
                })

        # Check accordion items (FAQ answers may have links)
        elif block_type == "accordion":
            for item in data.get("items", []):
                answer = item.get("answer", "")
                for match in anchor_pattern.finditer(answer):
                    full_tag = match.group(0)
                    url = match.group(1)
                    anchor_text = re.sub(r'<[^>]+>', '', match.group(2)).strip()

                    links.append({
                        "post_id": post_id,
                        "url": url,
                        "anchor_text": anchor_text[:255] if anchor_text else None,
                        "link_type": "internal" if is_internal_url(url) else "external",
                        "domain": extract_domain(url) if not is_internal_url(url) else None,
                        "opens_new_tab": bool(target_pattern.search(full_tag)),
                        "is_nofollow": bool(nofollow_pattern.search(full_tag)),
                    })

    return links


async def resolve_internal_link_post_ids(links: list[dict]) -> list[dict]:
    """Resolve internal URLs to their post IDs for the linked_post_id field."""
    internal_links = [l for l in links if l["link_type"] == "internal"]

    if not internal_links:
        return links

    # Extract unique slugs
    slug_to_links = {}
    for link in internal_links:
        slug = extract_slug_from_internal_url(link["url"])
        if slug:
            if slug not in slug_to_links:
                slug_to_links[slug] = []
            slug_to_links[slug].append(link)

    if not slug_to_links:
        return links

    # Batch query for all slugs
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # Query posts by slugs
            slugs = list(slug_to_links.keys())
            slugs_param = ",".join(slugs)

            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?slug=in.({slugs_param})&select=id,slug",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    posts = await resp.json()
                    slug_to_id = {p["slug"]: p["id"] for p in posts}

                    # Update links with post IDs
                    for slug, link_list in slug_to_links.items():
                        post_id = slug_to_id.get(slug)
                        for link in link_list:
                            link["linked_post_id"] = post_id
    except Exception:
        pass  # Continue without post IDs if query fails

    return links


async def save_post_links(post_id: str, content: list) -> int:
    """
    Extract links from content and save to blog_post_links table.
    Returns number of links saved.
    """
    links = extract_links_from_content(content, post_id)

    if not links:
        return 0

    # Resolve internal link post IDs
    links = await resolve_internal_link_post_ids(links)

    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # Delete existing links for this post (in case of update)
            async with session.delete(
                f"{SUPABASE_URL}/rest/v1/blog_post_links?post_id=eq.{post_id}",
                headers=headers
            ) as resp:
                pass  # Ignore result

            # Insert new links
            async with session.post(
                f"{SUPABASE_URL}/rest/v1/blog_post_links",
                headers=headers,
                json=links
            ) as resp:
                if resp.status in [200, 201]:
                    return len(links)
                return 0

    except Exception:
        return 0


# =============================================================================
# Backfill Tools - Update existing posts with better links
# =============================================================================

async def get_posts_needing_links(args: dict[str, Any]) -> dict[str, Any]:
    """
    Find published posts that have fewer internal links than recommended.
    Factors in catalog size - can't recommend more links than posts available.
    """
    try:
        limit = args.get("limit", 10)
        # Fetch more posts than requested to account for filtering
        fetch_limit = max(limit * 2, 100)

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # First, get total catalog size to determine realistic recommendations
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?select=id&status=eq.published",
                headers={**headers, "Prefer": "count=exact"}
            ) as resp:
                content_range = resp.headers.get("content-range", "")
                total_posts = 0
                if "/" in content_range:
                    try:
                        total_posts = int(content_range.split("/")[1])
                    except (ValueError, IndexError):
                        pass

            # Determine max achievable links based on catalog size
            # You can't link to more posts than exist (minus the current post)
            # Also apply practical caps based on catalog maturity
            if total_posts < 5:
                max_achievable = 1  # Very small catalog
                catalog_note = f"Small catalog ({total_posts} posts) - limited linking possible"
            elif total_posts < 15:
                max_achievable = 2  # Small catalog
                catalog_note = f"Growing catalog ({total_posts} posts) - moderate linking"
            elif total_posts < 30:
                max_achievable = 3  # Medium catalog
                catalog_note = f"Medium catalog ({total_posts} posts)"
            elif total_posts < 50:
                max_achievable = 4  # Good catalog
                catalog_note = None
            else:
                max_achievable = 6  # Large catalog - full potential
                catalog_note = None

            # Get published posts with their link counts
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?select=id,slug,title,reading_time,category_id&status=eq.published&order=created_at.asc&limit={fetch_limit}",
                headers=headers
            ) as resp:
                if resp.status != 200:
                    return {"content": [{"type": "text", "text": "Error fetching posts"}], "is_error": True}
                posts = await resp.json()

            if not posts:
                return {"content": [{"type": "text", "text": json.dumps({"posts": [], "message": "No published posts found"}, separators=(',', ':'))}]}

            # Get link counts for these posts
            post_ids = [p["id"] for p in posts]
            post_ids_param = ",".join(post_ids)

            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_post_links?select=post_id&post_id=in.({post_ids_param})&link_type=eq.internal",
                headers=headers
            ) as resp:
                links = await resp.json() if resp.status == 200 else []

            # Count links per post
            link_counts = {}
            for link in links:
                pid = link["post_id"]
                link_counts[pid] = link_counts.get(pid, 0) + 1

            # Find posts needing more links
            # Formula: ~3 internal links per 1000 words, BUT capped by catalog size
            posts_needing_links = []
            for post in posts:
                reading_time = post.get("reading_time") or 5
                # Word-based recommendation
                word_based = max(2, int(reading_time * 200 / 1000 * 3))
                # Cap by what's actually achievable given catalog size
                recommended = min(word_based, max_achievable)
                current = link_counts.get(post["id"], 0)
                deficit = recommended - current

                if deficit > 0:
                    posts_needing_links.append({
                        "id": post["id"],
                        "slug": post["slug"],
                        "title": post["title"][:60],  # Truncate for tokens
                        "current_links": current,
                        "recommended": recommended,
                        "deficit": deficit
                    })

            # Sort by deficit (most in need first) and limit
            posts_needing_links.sort(key=lambda x: x["deficit"], reverse=True)
            posts_needing_links = posts_needing_links[:limit]

            if not posts_needing_links:
                return {"content": [{"type": "text", "text": json.dumps({"posts": [], "message": "All posts have adequate internal links for current catalog size"}, separators=(',', ':'))}]}

            result = {"posts": posts_needing_links, "catalog_size": total_posts}
            if catalog_note:
                result["note"] = catalog_note

            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, separators=(',', ':'))
                }]
            }

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


async def get_post_for_linking(args: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch a post's full content for link enhancement.
    Returns content blocks and metadata needed for adding links.
    """
    try:
        post_id = args.get("post_id")
        if not post_id:
            return {"content": [{"type": "text", "text": "Error: post_id required"}], "is_error": True}

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?select=id,slug,title,excerpt,content,category_id,reading_time&id=eq.{post_id}",
                headers=headers
            ) as resp:
                if resp.status != 200:
                    return {"content": [{"type": "text", "text": "Error fetching post"}], "is_error": True}
                posts = await resp.json()

            if not posts:
                return {"content": [{"type": "text", "text": "Post not found"}], "is_error": True}

            post = posts[0]

            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "id": post["id"],
                        "slug": post["slug"],
                        "title": post["title"],
                        "excerpt": post["excerpt"],
                        "category_id": post["category_id"],
                        "content": post["content"]
                    }, separators=(',', ':'))
                }]
            }

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


async def update_post_content(args: dict[str, Any]) -> dict[str, Any]:
    """
    DEPRECATED: Use apply_link_insertions instead for safer link addition.
    This tool modifies content directly which risks unintended changes.
    """
    return {
        "content": [{
            "type": "text",
            "text": "Error: Use apply_link_insertions instead. It's safer - only wraps specified text in links without touching other content."
        }],
        "is_error": True
    }


async def apply_link_insertions(args: dict[str, Any]) -> dict[str, Any]:
    """
    Safely add links to a post by wrapping specific text phrases.

    Features:
    1. Fetches fresh content from database (no stale data)
    2. Only modifies exact text matches (no accidental changes)
    3. Context-aware validation - checks that anchor text in context makes sense
    4. Reports exactly what changed

    Each insertion can include:
    - anchor_text: The text to wrap in a link (required)
    - url: The link URL (required)
    - target_title: Title of target article (enables context validation)
    - anti_patterns: List of phrases to avoid (optional, for semantic disambiguation)
    - block_id: Optional specific block to target
    """
    try:
        post_id = args.get("post_id")
        insertions = args.get("insertions", [])

        if not post_id:
            return {"content": [{"type": "text", "text": "Error: post_id required"}], "is_error": True}
        if not insertions:
            return {"content": [{"type": "text", "text": "Error: insertions array required"}], "is_error": True}

        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # Fetch fresh content from database
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?id=eq.{post_id}&select=content",
                headers=headers
            ) as resp:
                if resp.status != 200:
                    return {"content": [{"type": "text", "text": "Error fetching post"}], "is_error": True}
                posts = await resp.json()

            if not posts:
                return {"content": [{"type": "text", "text": "Post not found"}], "is_error": True}

            content = posts[0].get("content", [])
            if not content:
                return {"content": [{"type": "text", "text": "Post has no content"}], "is_error": True}

            # Anti-pattern pre-filter - fast, deterministic check before API validation
            # Catches obvious semantic mismatches (e.g., "grip on the club" for a "grip technique" article)
            anti_pattern_rejected = []
            filtered_by_anti = []
            for ins in insertions:
                anti_patterns = ins.get("anti_patterns", [])
                if anti_patterns:
                    anchor_lower = ins.get("anchor_text", "").lower()
                    # Check if anchor text matches or is contained in any anti-pattern
                    matched_anti = None
                    for anti in anti_patterns:
                        anti_lower = anti.lower()
                        # Match if: anchor contains anti-pattern OR anti-pattern contains anchor
                        if anti_lower in anchor_lower or anchor_lower in anti_lower:
                            matched_anti = anti
                            break
                    if matched_anti:
                        anti_pattern_rejected.append({
                            "anchor": ins.get("anchor_text"),
                            "anti_pattern": matched_anti,
                            "target": ins.get("target_title", "unknown")
                        })
                        continue
                filtered_by_anti.append(ins)

            if anti_pattern_rejected:
                print(f"  → Anti-pattern filter rejected {len(anti_pattern_rejected)} link(s):")
                for rej in anti_pattern_rejected:
                    print(f"     ✗ \"{rej['anchor']}\" matches anti-pattern \"{rej['anti_pattern']}\"")

            insertions = filtered_by_anti

            # Anchor quality filter - reject overly generic anchors
            quality_rejected = []
            filtered_by_quality = []
            for ins in insertions:
                anchor = ins.get("anchor_text", "")
                if is_quality_anchor(anchor):
                    filtered_by_quality.append(ins)
                else:
                    quality_rejected.append({
                        "anchor": anchor,
                        "target": ins.get("target_title", "unknown"),
                        "reason": "too generic or short"
                    })

            if quality_rejected:
                print(f"  → Anchor quality filter rejected {len(quality_rejected)} link(s):")
                for rej in quality_rejected:
                    print(f"     ✗ \"{rej['anchor']}\" - {rej['reason']}")

            insertions = filtered_by_quality

            if not insertions:
                return {
                    "content": [{
                        "type": "text",
                        "text": "No links applied - all rejected (anti-pattern match or low anchor quality)"
                    }]
                }

            # Context validation phase - validate anchor text in context before applying
            # This prevents linking "topping" in "topping the leaderboard" to an article about golf topping
            insertions_with_titles = [i for i in insertions if i.get("target_title")]
            if insertions_with_titles:
                print(f"  → Validating {len(insertions_with_titles)} link context(s)...")
                validated_insertions = await validate_link_contexts_batch(
                    insertions_with_titles,
                    content
                )
                # Build set of validated (anchor_text, url) pairs
                validated_pairs = {(i["anchor_text"].lower(), i["url"]) for i in validated_insertions}

                # Filter original insertions to only validated ones
                context_rejected = []
                filtered_insertions = []
                for ins in insertions:
                    if ins.get("target_title"):
                        # Has title - check if validated
                        if (ins["anchor_text"].lower(), ins["url"]) in validated_pairs:
                            filtered_insertions.append(ins)
                        else:
                            context_rejected.append(ins)
                    else:
                        # No title - include without validation (backwards compatibility)
                        filtered_insertions.append(ins)

                if context_rejected:
                    print(f"  → Context filter rejected {len(context_rejected)} link(s):")
                    for rej in context_rejected:
                        target = rej.get('target_title', 'unknown')[:40]
                        print(f"     ✗ \"{rej['anchor_text']}\" → \"{target}\" (context/specificity mismatch)")

                insertions = filtered_insertions

            if not insertions:
                return {
                    "content": [{
                        "type": "text",
                        "text": "No links applied - all failed context validation (anchor text used in wrong context)"
                    }]
                }

            # Apply insertions
            applied = []
            failed = []

            def find_and_replace_case_insensitive(text: str, search: str, url: str) -> tuple[str, str | None]:
                """
                Find search text case-insensitively, replace with link preserving original case.
                Returns (new_text, matched_text) or (original_text, None) if not found.
                """
                search_lower = search.lower()
                text_lower = text.lower()

                # Check if already linked
                if f'>{search}</a>'.lower() in text_lower:
                    return text, None

                # Find the position case-insensitively
                pos = text_lower.find(search_lower)
                if pos == -1:
                    return text, None

                # Extract the original-case version from the text
                original_match = text[pos:pos + len(search)]

                # Build link with original casing
                link_html = f'<a href="{url}">{original_match}</a>'

                # Replace first occurrence
                new_text = text[:pos] + link_html + text[pos + len(search):]
                return new_text, original_match

            for insertion in insertions:
                anchor_text = insertion.get("anchor_text", "").strip()
                url = insertion.get("url", "").strip()
                block_id = insertion.get("block_id")  # Optional: target specific block

                if not anchor_text or not url:
                    failed.append({"anchor_text": anchor_text, "reason": "missing anchor_text or url"})
                    continue

                # Find and replace the text (first occurrence only, case-insensitive)
                found = False
                for block in content:
                    # Skip if block_id specified and doesn't match
                    if block_id and block.get("id") != block_id:
                        continue

                    block_type = block.get("type", "")
                    data = block.get("data", {})

                    # Check paragraph text
                    if block_type == "paragraph":
                        text = data.get("text", "")
                        new_text, matched = find_and_replace_case_insensitive(text, anchor_text, url)
                        if matched:
                            data["text"] = new_text
                            applied.append({"anchor_text": matched, "url": url, "block_id": block.get("id")})
                            found = True
                            break

                    # Check list items
                    elif block_type == "list":
                        items = data.get("items", [])
                        for i, item in enumerate(items):
                            if isinstance(item, str):
                                new_item, matched = find_and_replace_case_insensitive(item, anchor_text, url)
                                if matched:
                                    items[i] = new_item
                                    applied.append({"anchor_text": matched, "url": url, "block_id": block.get("id")})
                                    found = True
                                    break
                        if found:
                            break

                    # Check callout text
                    elif block_type == "callout":
                        text = data.get("text", "")
                        new_text, matched = find_and_replace_case_insensitive(text, anchor_text, url)
                        if matched:
                            data["text"] = new_text
                            applied.append({"anchor_text": matched, "url": url, "block_id": block.get("id")})
                            found = True
                            break

                if not found:
                    failed.append({"anchor_text": anchor_text, "reason": "text not found or already linked"})

            if not applied:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"No links applied. Failed: {json.dumps(failed, separators=(',', ':'))}"
                    }]
                }

            # Save updated content with updated_at to trigger webhooks
            from datetime import datetime, timezone
            async with session.patch(
                f"{SUPABASE_URL}/rest/v1/blog_posts?id=eq.{post_id}",
                headers=headers,
                json={
                    "content": content,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            ) as resp:
                if resp.status not in [200, 204]:
                    error = await resp.text()
                    return {"content": [{"type": "text", "text": f"Error saving: {error}"}], "is_error": True}

        # Re-extract and save links to tracking table
        links_saved = await save_post_links(post_id, content)

        # Log applied links
        if applied:
            print(f"  → Applied {len(applied)} link(s):")
            for link in applied:
                url_short = link['url'].split('/')[-1][:30]
                print(f"     ✓ \"{link['anchor_text']}\" → {url_short}")
        if failed:
            print(f"  → Skipped {len(failed)} pattern(s) (not found in content)")

        result = {
            "applied": len(applied),
            "links": applied,
            "total_tracked": links_saved
        }
        if failed:
            result["failed"] = failed

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result, separators=(',', ':'))
            }]
        }

    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "is_error": True}


async def remove_internal_links_from_post(post_id: str) -> dict[str, Any]:
    """
    Remove all internal links from a post's content.
    Used to clean up bad links before re-running backfill.

    Returns count of links removed.
    """
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # Fetch post content
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?id=eq.{post_id}&select=id,slug,content",
                headers=headers
            ) as resp:
                if resp.status != 200:
                    return {"success": False, "error": "Failed to fetch post"}
                posts = await resp.json()

            if not posts:
                return {"success": False, "error": "Post not found"}

            post = posts[0]
            content = post.get("content", [])
            if not content:
                return {"success": True, "removed": 0, "message": "No content"}

            # Regex to match internal links: <a href="/...">text</a>
            # Captures the inner text to preserve it
            internal_link_pattern = re.compile(r'<a\s+href="(/[^"]*)"[^>]*>([^<]*)</a>', re.IGNORECASE)

            removed_count = 0

            def strip_internal_links(text: str) -> tuple[str, int]:
                """Remove internal links, return cleaned text and count."""
                count = len(internal_link_pattern.findall(text))
                # Replace link with just the anchor text
                cleaned = internal_link_pattern.sub(r'\2', text)
                return cleaned, count

            # Process each block
            for block in content:
                block_type = block.get("type", "")
                data = block.get("data", {})

                if block_type == "paragraph":
                    text = data.get("text", "")
                    cleaned, count = strip_internal_links(text)
                    if count > 0:
                        data["text"] = cleaned
                        removed_count += count

                elif block_type == "list":
                    items = data.get("items", [])
                    for i, item in enumerate(items):
                        if isinstance(item, str):
                            cleaned, count = strip_internal_links(item)
                            if count > 0:
                                items[i] = cleaned
                                removed_count += count

                elif block_type == "callout":
                    text = data.get("text", "")
                    cleaned, count = strip_internal_links(text)
                    if count > 0:
                        data["text"] = cleaned
                        removed_count += count

            if removed_count == 0:
                return {"success": True, "removed": 0, "message": "No internal links found"}

            # Save cleaned content with updated_at to trigger webhooks
            from datetime import datetime, timezone
            async with session.patch(
                f"{SUPABASE_URL}/rest/v1/blog_posts?id=eq.{post_id}",
                headers=headers,
                json={
                    "content": content,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            ) as resp:
                if resp.status not in [200, 204]:
                    return {"success": False, "error": "Failed to save cleaned content"}

            # Delete internal link records from tracking table
            async with session.delete(
                f"{SUPABASE_URL}/rest/v1/blog_post_links?post_id=eq.{post_id}&link_type=eq.internal",
                headers=headers
            ) as resp:
                pass  # Best effort - table might not exist

            return {
                "success": True,
                "removed": removed_count,
                "post_slug": post["slug"]
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def remove_single_link_by_id(link_id: str) -> dict[str, Any]:
    """
    Remove a single link from a post by its blog_post_links.id.

    This:
    1. Fetches the link record to get URL and post_id
    2. Removes the <a> tag from the post content (preserving anchor text)
    3. Deletes the link record from blog_post_links table

    Args:
        link_id: The UUID from the blog_post_links table

    Returns:
        Dict with success status and details
    """
    try:
        async with aiohttp.ClientSession() as session:
            headers = get_supabase_headers()

            # Fetch the link record
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_post_links?id=eq.{link_id}&select=id,post_id,url,anchor_text,link_type",
                headers=headers
            ) as resp:
                if resp.status != 200:
                    return {"success": False, "error": "Failed to fetch link record"}
                links = await resp.json()

            if not links:
                return {"success": False, "error": f"Link with ID '{link_id}' not found"}

            link_record = links[0]
            post_id = link_record["post_id"]
            url = link_record["url"]
            anchor_text = link_record.get("anchor_text", "")
            link_type = link_record.get("link_type", "unknown")

            # Fetch the post content
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?id=eq.{post_id}&select=id,slug,content",
                headers=headers
            ) as resp:
                if resp.status != 200:
                    return {"success": False, "error": "Failed to fetch post"}
                posts = await resp.json()

            if not posts:
                return {"success": False, "error": "Post not found"}

            post = posts[0]
            content = post.get("content", [])

            if not content:
                # No content, just delete the link record
                async with session.delete(
                    f"{SUPABASE_URL}/rest/v1/blog_post_links?id=eq.{link_id}",
                    headers=headers
                ) as resp:
                    pass
                return {"success": True, "removed": True, "post_slug": post["slug"], "message": "Link record deleted (post has no content)"}

            # Build regex to match this specific link
            # Escape special regex characters in URL
            escaped_url = re.escape(url)
            # Match <a> tag with this exact href
            link_pattern = re.compile(
                rf'<a\s+[^>]*href=["\']({escaped_url})["\'][^>]*>([^<]*)</a>',
                re.IGNORECASE
            )

            removed = False

            def strip_specific_link(text: str) -> tuple[str, bool]:
                """Remove the specific link, return cleaned text and whether it was found."""
                match = link_pattern.search(text)
                if match:
                    # Replace link with just the anchor text
                    cleaned = link_pattern.sub(r'\2', text, count=1)
                    return cleaned, True
                return text, False

            # Process each block
            for block in content:
                if removed:
                    break

                block_type = block.get("type", "")
                data = block.get("data", {})

                if block_type == "paragraph":
                    text = data.get("text", "")
                    cleaned, found = strip_specific_link(text)
                    if found:
                        data["text"] = cleaned
                        removed = True

                elif block_type == "list":
                    items = data.get("items", [])
                    for i, item in enumerate(items):
                        if isinstance(item, str):
                            cleaned, found = strip_specific_link(item)
                            if found:
                                items[i] = cleaned
                                removed = True
                                break

                elif block_type == "callout":
                    text = data.get("text", "")
                    cleaned, found = strip_specific_link(text)
                    if found:
                        data["text"] = cleaned
                        removed = True

                elif block_type == "accordion":
                    for item in data.get("items", []):
                        answer = item.get("answer", "")
                        cleaned, found = strip_specific_link(answer)
                        if found:
                            item["answer"] = cleaned
                            removed = True
                            break

            # Save updated content if we removed the link
            if removed:
                async with session.patch(
                    f"{SUPABASE_URL}/rest/v1/blog_posts?id=eq.{post_id}",
                    headers=headers,
                    json={
                        "content": content,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                ) as resp:
                    if resp.status not in [200, 204]:
                        return {"success": False, "error": "Failed to save updated content"}

            # Delete the link record from tracking table
            async with session.delete(
                f"{SUPABASE_URL}/rest/v1/blog_post_links?id=eq.{link_id}",
                headers=headers
            ) as resp:
                if resp.status not in [200, 204]:
                    return {"success": False, "error": "Failed to delete link record"}

            return {
                "success": True,
                "removed_from_content": removed,
                "post_slug": post["slug"],
                "url": url,
                "anchor_text": anchor_text,
                "link_type": link_type
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def cleanup_internal_links(post_slugs: list[str] = None, all_posts: bool = False) -> list[dict]:
    """
    Remove internal links from specified posts or all posts.

    Args:
        post_slugs: List of post slugs to clean up
        all_posts: If True, clean all published posts

    Returns:
        List of results for each post
    """
    results = []

    async with aiohttp.ClientSession() as session:
        headers = get_supabase_headers()

        if all_posts:
            # Get all published posts
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?select=id,slug&status=eq.published",
                headers=headers
            ) as resp:
                if resp.status != 200:
                    return [{"error": "Failed to fetch posts"}]
                posts = await resp.json()
        elif post_slugs:
            # Get specific posts
            slugs_param = ",".join(f'"{s}"' for s in post_slugs)
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/blog_posts?select=id,slug&slug=in.({slugs_param})",
                headers=headers
            ) as resp:
                if resp.status != 200:
                    return [{"error": "Failed to fetch posts"}]
                posts = await resp.json()
        else:
            return [{"error": "Specify post_slugs or all_posts=True"}]

        for post in posts:
            result = await remove_internal_links_from_post(post["id"])
            result["slug"] = post["slug"]
            results.append(result)

    return results


# =============================================================================
# Tool Definitions
# =============================================================================

LINK_TOOLS = [
    {
        "name": "get_internal_link_suggestions",
        "description": "Find semantically relevant posts for internal linking. Uses AI to filter out unrelated posts. Returns suggestions with anchor_patterns (phrases to link), anti_patterns (phrases to avoid), and semantic_intent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The source post title or topic (used for relevance matching)"
                },
                "source_excerpt": {
                    "type": "string",
                    "description": "Brief description of the source post (improves relevance scoring)"
                },
                "category_id": {
                    "type": "string",
                    "description": "Category UUID to prioritize same-category posts"
                },
                "exclude_slug": {
                    "type": "string",
                    "description": "Slug of current post to exclude from results"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max suggestions (default 8, max 15)"
                }
            },
            "required": ["topic"]
        },
        "function": get_internal_link_suggestions
    },
    {
        "name": "validate_urls",
        "description": "Verify URLs are valid before publishing. Internal URLs checked against database, external via HTTP. Call before create_blog_post.",
        "input_schema": {
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "URLs to validate (internal and external)"
                }
            },
            "required": ["urls"]
        },
        "function": validate_urls
    }
]

# Backfill tools - used in --backfill-links mode
BACKFILL_LINK_TOOLS = [
    {
        "name": "get_posts_needing_links",
        "description": "Find published posts with fewer internal links than recommended. Returns posts sorted by link deficit.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max posts to return (default 10)"
                }
            },
            "required": []
        },
        "function": get_posts_needing_links
    },
    {
        "name": "get_post_for_linking",
        "description": "Fetch a post's full content for link enhancement. Use before modifying content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {
                    "type": "string",
                    "description": "Post UUID to fetch"
                }
            },
            "required": ["post_id"]
        },
        "function": get_post_for_linking
    },
    {
        "name": "get_internal_link_suggestions",
        "description": "Find semantically relevant posts for internal linking. Uses AI to filter out unrelated posts. Returns suggestions with anchor_patterns (phrases to link), anti_patterns (phrases to avoid), and semantic_intent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The source post title (used for relevance scoring)"
                },
                "source_excerpt": {
                    "type": "string",
                    "description": "Brief description of the source post (improves relevance scoring)"
                },
                "category_id": {
                    "type": "string",
                    "description": "Category UUID to prioritize same-category posts"
                },
                "exclude_slug": {
                    "type": "string",
                    "description": "Slug of current post to exclude"
                }
            },
            "required": ["topic"]
        },
        "function": get_internal_link_suggestions
    },
    {
        "name": "validate_urls",
        "description": "Verify URLs are valid. Internal URLs checked against database, external via HTTP.",
        "input_schema": {
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "URLs to validate"
                }
            },
            "required": ["urls"]
        },
        "function": validate_urls
    },
    {
        "name": "apply_link_insertions",
        "description": "Safely add links with semantic validation. Verifies anchor text meaning matches target article before linking. Include target_title and anti_patterns for best results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_id": {
                    "type": "string",
                    "description": "Post UUID to update"
                },
                "insertions": {
                    "type": "array",
                    "description": "List of links to add. Include target_title and anti_patterns for semantic validation.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "anchor_text": {"type": "string", "description": "Exact text to wrap in a link"},
                            "url": {"type": "string", "description": "URL for the link (e.g., /blog/post-slug)"},
                            "target_title": {"type": "string", "description": "Title of target article (enables context validation)"},
                            "anti_patterns": {"type": "array", "items": {"type": "string"}, "description": "Phrases to avoid linking (from suggestion's anti_patterns)"},
                            "block_id": {"type": "string", "description": "Optional: target specific block by ID"}
                        },
                        "required": ["anchor_text", "url", "target_title"]
                    }
                }
            },
            "required": ["post_id", "insertions"]
        },
        "function": apply_link_insertions
    }
]
