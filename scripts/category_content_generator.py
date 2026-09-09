#!/usr/bin/env python3
"""
category_content_generator.py
Expands the 8 category hub pages (/communication/, /design/, etc.) with
unique long-form content: a 150-250 word intro on choosing an open-source
alternative in that category, plus a 3-item FAQ — targeting real editorial
substance instead of the current bare link-list (~77 words).

Waterfall (matches generate_comparison.py / migrate_content_generator.py):
  Primary:  Groq (openai/gpt-oss-120b)   — free, fast
  Fallback: Google Gemini 2.5 Flash-Lite — free, reliable

Both providers are checked for truncation (finish_reason == 'length' for
Groq, finishReason == 'MAX_TOKENS' for Gemini) before their output is
accepted — a truncated response is treated as a failure and falls through
to the next provider, rather than being cached as-is. This is the same
fix applied to generate_comparison.py after a comparison page shipped with
a Migration Path list cut off mid-sentence: nothing was checking whether
the API actually finished before caching its output.

Output is cached to data/cache/category_content.json, keyed by category
slug (e.g. "communication"). The category-page loop in
publish_github_pages.py reads this cache and renders the expanded intro +
FAQ when present, falling back to the existing bare list for any category
not yet processed. Re-running this script skips categories that already
have cached content, so it's cheap and safe to re-run later.

USAGE:
    # Offline dry run — no API calls, writes placeholder content so you can
    # test the build pipeline without spending API quota
    python3 scripts/category_content_generator.py --mock

    # Full run — all 8 categories (only ~8 API calls total, cheap)
    python3 scripts/category_content_generator.py

    # Regenerate a specific category even if already cached
    python3 scripts/category_content_generator.py --slugs communication --force
"""
import argparse
import glob
import json
import logging
import os
import re
import sys
import time

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

CACHE_PATH = "data/cache/category_content.json"
COMPARISONS_GLOB = "data/cache/comparisons_*.json"

# Kept in sync with CATEGORY_ICONS in publish_github_pages.py. 'general' is a
# catch-all bucket, not a real editorial category, so it's excluded here.
CATEGORIES = [
    "communication",
    "productivity",
    "developer-tools",
    "design",
    "project-management",
    "file-storage",
    "video-conferencing",
]


def load_comparisons():
    pairs = []
    for path in sorted(glob.glob(COMPARISONS_GLOB)):
        with open(path) as f:
            data = json.load(f)
        items = data.get("comparisons", data) if isinstance(data, dict) else data
        pairs.extend(items)
    return pairs


def load_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def build_prompt(category, tool_pairs):
    label = category.replace("-", " ")
    pair_lines = "\n".join(
        f"- {c.get('proprietary_tool')} → {c.get('oss_tool')}" for c in tool_pairs[:8]
    ) or f"- (general {label} tools)"
    return f"""You are writing the intro content for a hub page listing open-source
alternatives to popular {label} tools. This page lists these specific comparisons:

{pair_lines}

Respond with ONLY valid JSON (no markdown fences, no preamble, no text before or after)
in this exact structure:

{{
  "intro": "150-250 words on why teams look for open-source {label} alternatives, what to weigh when choosing one (e.g. self-hosting effort, data ownership, feature parity, team size), and what this page covers. Be specific to {label} tools, not generic filler that could apply to any software category.",
  "faq": [
    {{"q": "a real question someone comparing open-source {label} tools would search", "a": "2-3 sentence direct answer"}}
  ]
}}

Include exactly 3 items in "faq". Total content across both fields should be 250-350 words.

Do NOT begin the intro with the sentence pattern "Looking for [category] alternatives is a/an [adjective] move for [audience]..." or "In today's digital landscape..." — write like a senior engineer explaining a real tradeoff to a peer, not marketing copy. No markdown formatting inside the JSON string values."""


GROQ_QUOTA_EXHAUSTED = False
GROQ_MAX_SLEEP = 20


class GroqQuotaExhausted(Exception):
    pass


def generate_with_groq(prompt: str, retries: int = 2) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set")
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "openai/gpt-oss-120b",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1500,  # 250-350 words + JSON overhead; generous headroom
                    "temperature": 0.6,
                },
                timeout=30,
            )
            response.raise_for_status()
            choice = response.json()["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ValueError(
                    "Groq response truncated (finish_reason=length) — "
                    "treating as a failure so the fallback chain runs"
                )
            return choice["message"]["content"]
        except requests.exceptions.HTTPError as e:
            last_error = e
            if response.status_code == 429:
                wait = int(response.headers.get("retry-after", 15))
                if wait > GROQ_MAX_SLEEP:
                    raise GroqQuotaExhausted(
                        f"Groq asked for a {wait}s wait (likely daily quota exhausted, "
                        f"not a transient rate limit) — skipping Groq for the rest of this run"
                    )
                if attempt < retries:
                    logger.info(f"    Groq rate-limited, waiting {wait}s before retry {attempt + 1}/{retries}")
                    time.sleep(wait)
                    continue
            raise
        except (ValueError, KeyError) as e:
            last_error = e
            if attempt < retries:
                time.sleep(5)
                continue
            raise
    raise last_error


def generate_with_gemini(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 1500},
        },
        timeout=30,
    )
    response.raise_for_status()
    candidate = response.json()["candidates"][0]
    if candidate.get("finishReason") == "MAX_TOKENS":
        raise ValueError(
            "Gemini response truncated (finishReason=MAX_TOKENS) — "
            "treating as a failure so it falls through to the template fallback"
        )
    return candidate["content"]["parts"][0]["text"]


def parse_json_response(raw: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.M)
    return json.loads(cleaned)


def mock_content(category):
    label = category.replace("-", " ")
    return {
        "intro": (f"[MOCK] Placeholder intro paragraph about open-source {label} alternatives. " * 8).strip(),
        "faq": [
            {"q": f"[MOCK] Question {i} about {label} alternatives?", "a": f"[MOCK] Answer {i}."}
            for i in range(1, 4)
        ],
    }


def generate_for_category(category, tool_pairs, mock=False):
    global GROQ_QUOTA_EXHAUSTED
    if mock:
        return mock_content(category)
    prompt = build_prompt(category, tool_pairs)

    if not GROQ_QUOTA_EXHAUSTED:
        for attempt in range(2):
            try:
                raw = generate_with_groq(prompt)
                return parse_json_response(raw)
            except GroqQuotaExhausted as e:
                logger.warning(f"    {e}")
                GROQ_QUOTA_EXHAUSTED = True
                break
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"    Groq attempt 1 failed ({e}), retrying...")
                    time.sleep(3)
                else:
                    logger.warning(f"    Groq attempt 2 failed ({e}), falling back to Gemini")

    try:
        raw = generate_with_gemini(prompt)
        return parse_json_response(raw)
    except Exception as e:
        logger.error(f"Gemini also failed ({e}) — skipping this category")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", default=None, help="Comma-separated list of specific category slugs to (re)generate")
    ap.add_argument("--force", action="store_true", help="Regenerate even if already cached")
    ap.add_argument("--mock", action="store_true", help="Offline dry run — no API calls, writes placeholder content")
    ap.add_argument("--sleep", type=float, default=8.0, help="Seconds to sleep between API calls")
    args = ap.parse_args()

    all_comps = load_comparisons()
    cache = load_cache()
    wanted_slugs = set(args.slugs.split(",")) if args.slugs else None

    todo = []
    for category in CATEGORIES:
        if wanted_slugs and category not in wanted_slugs:
            continue
        if not args.force and category in cache:
            continue
        tool_pairs = [c for c in all_comps if c.get("category") == category]
        todo.append((category, tool_pairs))

    if not todo:
        logger.info("Nothing to do — all categories already cached. Use --force to regenerate.")
        return

    logger.info(f"Generating expanded content for {len(todo)} categor{'y' if len(todo)==1 else 'ies'}{' [MOCK MODE]' if args.mock else ''}")

    ok, failed = 0, 0
    for i, (category, tool_pairs) in enumerate(todo, 1):
        logger.info(f"[{i}/{len(todo)}] {category} ({len(tool_pairs)} comparisons)")
        content = generate_for_category(category, tool_pairs, mock=args.mock)
        if content:
            cache[category] = content
            ok += 1
            save_cache(cache)
        else:
            failed += 1
        if not args.mock and i < len(todo):
            time.sleep(args.sleep)

    logger.info(f"Done. {ok} succeeded, {failed} failed. Cache: {CACHE_PATH}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
