#!/usr/bin/env python3
"""
fix_gemini_alias_and_resilience.py
Follow-up fix to fix_deprecated_ai_models.py. That patch swapped Gemini's
dead gemini-1.5-flash for gemini-2.5-flash-lite, but the "Expand Thin
Migrate Pages" test run showed gemini-2.5-flash-lite ALSO 404ing in
practice. Rather than chase another dated model name, this switches to
gemini-flash-lite-latest — a Google-maintained alias that always points
to their current Flash-Lite release, specifically so callers don't have
to keep updating this every time Google retires a dated model.

Also adds retry-with-backoff to the Groq call. The same test run showed
Groq 429 (rate limit) and an occasional empty-response error on the free
tier's 8,000 TPM cap when firing requests back-to-back. This adds one
retry with backoff (respecting Groq's Retry-After header when present)
before falling through to Gemini.

Run this AFTER fix_deprecated_ai_models.py (or after re-running it if
you haven't yet). Safe to re-run — skips if already applied.

USAGE:
    python3 fix_gemini_alias_and_resilience.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET = "scripts/generate_comparison.py"

OLD_BLOCK = """def generate_with_groq(prompt: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError('GROQ_API_KEY not set')
    response = requests.post(
        'https://api.groq.com/openai/v1/chat/completions',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={
            'model': 'openai/gpt-oss-120b',
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 2500,
            'temperature': 0.6
        },
        timeout=30
    )
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content']


def generate_with_gemini(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError('GEMINI_API_KEY not set')
    response = requests.post(
        f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}',
        headers={'Content-Type': 'application/json'},
        json={'contents': [{'parts': [{'text': prompt}]}]},"""

NEW_BLOCK = """def generate_with_groq(prompt: str, retries: int = 2) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError('GROQ_API_KEY not set')
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                json={
                    'model': 'openai/gpt-oss-120b',
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 2500,
                    'temperature': 0.6
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except requests.exceptions.HTTPError as e:
            last_error = e
            if response.status_code == 429 and attempt < retries:
                wait = int(response.headers.get('retry-after', 15))
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
        raise ValueError('GEMINI_API_KEY not set')
    # gemini-flash-lite-latest is Google's self-updating alias for their current
    # Flash-Lite release. Pinning to a dated model name is what broke this twice
    # in one week (gemini-1.5-flash, then gemini-2.5-flash-lite) — the alias is
    # maintained specifically so callers don't have to chase every retirement.
    response = requests.post(
        f'https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={api_key}',
        headers={'Content-Type': 'application/json'},
        json={'contents': [{'parts': [{'text': prompt}]}]},"""


def main():
    path = os.path.join(ROOT, TARGET)
    if not os.path.exists(path):
        print(f"ERROR: {TARGET} not found. Run this from the repo root.")
        sys.exit(1)

    with open(path) as f:
        src = f.read()

    if "gemini-flash-lite-latest" in src:
        print(f"SKIP: {TARGET} already patched.")
        return

    if "gemini-1.5-flash" in src:
        print("NOTE: this file still has the original gemini-1.5-flash / llama-3.3-70b-versatile\n"
              "strings — run fix_deprecated_ai_models.py FIRST, then run this script.")
        sys.exit(1)

    if OLD_BLOCK not in src:
        print("ERROR: could not find the expected block to patch. Your file may have been\n"
              "modified differently than expected. No changes written — check manually.")
        sys.exit(1)

    src = src.replace(OLD_BLOCK, NEW_BLOCK)

    with open(path, "w") as f:
        f.write(src)

    print(f"Patched: {TARGET}")
    print("  - Gemini now uses the self-updating gemini-flash-lite-latest alias")
    print("  - Groq now retries once on 429 (respecting Retry-After) or empty response")


if __name__ == "__main__":
    main()
