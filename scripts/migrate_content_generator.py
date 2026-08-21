#!/usr/bin/env python3
"""
migrate_content_generator.py
Expands thin migrate-*/index.html pages with unique long-form content: an
intro on why/when to migrate, detailed step explanations, a common-pitfalls
section, and an FAQ — targeting 500-700 words of genuinely unique content
per page (AdSense's thin-content bar is roughly 200 words).

Waterfall (matches generate_comparison.py):
  Primary:  Groq (openai/gpt-oss-120b)   — free, fast
  Fallback: Google Gemini 2.5 Flash-Lite — free, reliable

Output is cached to data/cache/migrate_content.json, keyed by
"{prop_key}-to-{oss_key}". build_migration_page() in publish_github_pages.py
reads this cache and renders the expanded sections when present, falling
back to the existing short version for pairs not yet processed. Re-running
this script skips pairs that already have cached content, so it's cheap
and safe to re-run as new comparison pairs get added later.

USAGE:
    # Test run — only the first 4 pairs missing content. Do this first.
    python3 scripts/migrate_content_generator.py --limit 4

    # Full run — every pair still missing cached content
    python3 scripts/migrate_content_generator.py

    # Regenerate specific pairs even if already cached
    python3 scripts/migrate_content_generator.py --slugs figma-to-penpot,slack-to-element --force

    # Offline dry run — no API calls, writes placeholder content so you can
    # test the build + audit pipeline without spending API quota
    python3 scripts/migrate_content_generator.py --limit 4 --mock
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

CACHE_PATH = "data/cache/migrate_content.json"
COMPARISONS_GLOB = "data/cache/comparisons_*.json"


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


def build_prompt(comp):
    prop = comp.get("proprietary_tool", "")
    oss = comp.get("oss_tool", "")
    prop_pricing = comp.get("proprietary_pricing", "a paid plan")
    category = comp.get("category", "software")
    return f"""You are writing long-form, original content for a migration guide page titled "How to Migrate from {prop} to {oss}".

This is a {category} tool. {prop} costs {prop_pricing}; {oss} is a free/open-source alternative.

Respond with ONLY valid JSON (no markdown fences, no preamble, no text before or after) in this exact structure:

{{
  "intro": "2-3 paragraphs (150-200 words total) on why and when someone would migrate from {prop} to {oss}. Be specific to these two tools, not generic filler.",
  "steps": [
    {{"title": "short step title", "detail": "2-4 sentences elaborating on this step, specific to {prop} and {oss}"}}
  ],
  "challenges": [
    {{"issue": "a real challenge someone migrating from {prop} to {oss} would hit", "solution": "1-2 sentences on how to handle it"}}
  ],
  "faq": [
    {{"q": "a real question someone would search when considering this migration", "a": "2-3 sentence answer"}}
  ]
}}

Include 5-6 items in "steps" (covering export, setup, import, team onboarding, and cutover), 3 items in "challenges", and 3 items in "faq".
Total content across all fields should be 500-700 words. Be concrete and specific to {prop} and {oss} — avoid generic phrasing that could apply to any software migration. No markdown formatting inside the JSON string values."""


GROQ_QUOTA_EXHAUSTED = False  # set once we see a long retry-after — see generate_with_groq
GROQ_MAX_SLEEP = 20  # never actually sleep longer than this for a single retry, regardless of what the API asks for


class GroqQuotaExhausted(Exception):
    """Raised when Groq's retry-after suggests the daily quota is spent, not a
    transient per-minute throttle. Sleeping through a multi-minute wait here
    is what caused a 55-pair run to blow past GitHub Actions' 6-hour job
    timeout and get force-canceled with zero progress committed. Once we see
    this, we stop calling Groq for the rest of the run and go straight to
    Gemini instead of repeating the same multi-hundred-second wait per pair."""
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
                    "max_tokens": 2200,  # 500-700 words of content + JSON structure overhead (keys, quotes, braces) needs real headroom — 1400 was truncating responses mid-string
                    "temperature": 0.6,
                },
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except requests.exceptions.HTTPError as e:
            last_error = e
            if response.status_code == 429:
                wait = int(response.headers.get("retry-after", 15))
                if wait > GROQ_MAX_SLEEP:
                    # A wait this long means the daily token/request quota is spent,
                    # not a per-minute throttle — waiting it out here would block the
                    # whole batch. Bail immediately; caller falls through to Gemini.
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
            # Empty or malformed body (occasionally returned under load) — retry once.
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
        # gemini-flash-lite-latest is Google's self-updating alias for their current
        # Flash-Lite release. Pinning to a dated model name (e.g. gemini-2.5-flash-lite)
        # is what broke this whole pipeline in the first place — Google retires dated
        # names on a rolling basis. The alias is maintained specifically so callers
        # don't have to chase this.
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]


def parse_json_response(raw: str) -> dict:
    # Strip markdown fences if the model added them despite instructions.
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.M)
    return json.loads(cleaned)


def mock_content(comp):
    """Deterministic offline placeholder — lets you test the build/audit
    pipeline end-to-end with zero API calls before spending real quota."""
    prop, oss = comp.get("proprietary_tool", "Tool A"), comp.get("oss_tool", "Tool B")
    return {
        "intro": (f"[MOCK] Placeholder intro paragraph about migrating from {prop} to {oss}. " * 6).strip(),
        "steps": [
            {"title": f"Mock step {i}", "detail": (f"[MOCK] Detail for step {i} about {prop} to {oss}. " * 3).strip()}
            for i in range(1, 6)
        ],
        "challenges": [
            {"issue": f"[MOCK] Challenge {i} for {prop} to {oss}", "solution": f"[MOCK] Solution {i}."}
            for i in range(1, 4)
        ],
        "faq": [
            {"q": f"[MOCK] Question {i} about {prop} vs {oss}?", "a": f"[MOCK] Answer {i}."}
            for i in range(1, 4)
        ],
    }


def generate_for_pair(comp, mock=False):
    global GROQ_QUOTA_EXHAUSTED
    if mock:
        return mock_content(comp)
    prompt = build_prompt(comp)

    if not GROQ_QUOTA_EXHAUSTED:
        # Retry the full call+parse cycle on Groq — a truncated or malformed JSON
        # response is often a one-off generation quirk, not a systemic failure,
        # and is worth a fresh attempt before giving up on Groq entirely.
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
        logger.error(f"Gemini also failed ({e}) — skipping this pair")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="Only process the first N pairs missing content")
    ap.add_argument("--slugs", default=None, help="Comma-separated list of specific pair slugs (prop-to-oss) to (re)generate")
    ap.add_argument("--force", action="store_true", help="Regenerate even if already cached")
    ap.add_argument("--mock", action="store_true", help="Offline dry run — no API calls, writes placeholder content")
    ap.add_argument("--sleep", type=float, default=8.0, help="Seconds to sleep between API calls (rate-limit friendly — Groq free tier is 8,000 TPM)")
    args = ap.parse_args()

    pairs = load_comparisons()
    if not pairs:
        logger.error(f"No comparison data found matching {COMPARISONS_GLOB} — nothing to generate content for.")
        sys.exit(1)

    cache = load_cache()
    wanted_slugs = set(args.slugs.split(",")) if args.slugs else None

    todo = []
    for comp in pairs:
        key = f"{comp.get('proprietary_key')}-to-{comp.get('oss_key')}"
        if wanted_slugs and key not in wanted_slugs:
            continue
        if not args.force and key in cache:
            continue
        todo.append((key, comp))

    if args.limit:
        todo = todo[: args.limit]

    if not todo:
        logger.info("Nothing to do — all matching pairs already cached. Use --force to regenerate.")
        return

    logger.info(f"Generating expanded content for {len(todo)} pair(s){' [MOCK MODE]' if args.mock else ''}")

    ok, failed = 0, 0
    for i, (key, comp) in enumerate(todo, 1):
        logger.info(f"[{i}/{len(todo)}] {key}")
        content = generate_for_pair(comp, mock=args.mock)
        if content:
            cache[key] = content
            ok += 1
            save_cache(cache)  # incremental save — a mid-run failure won't lose progress
        else:
            failed += 1
        if not args.mock and i < len(todo):
            time.sleep(args.sleep)

    logger.info(f"Done. {ok} succeeded, {failed} failed. Cache: {CACHE_PATH}")
    if GROQ_QUOTA_EXHAUSTED:
        logger.info("Note: Groq's daily quota appeared exhausted partway through this run — "
                     "remaining pairs were generated via Gemini only. This should reset on Groq's next daily cycle.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
