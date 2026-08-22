#!/usr/bin/env python3
"""
fix_groq_uncapped_sleep.py
URGENT — fixes the bug currently stalling your live "Open Source Alternative
Pipeline" run. The retry-after fix added earlier (fix_gemini_alias_and_resilience.py)
had no upper bound on the sleep duration. Groq is currently returning
retry-after values around 1250-1360 seconds (~21-22 min), and the old code
slept through every single one, on every comparison, in every parallel batch —
which is why the run has been going for over an hour and is still on
comparison #4 of batch 1 of 7.

This patch:
  1. Caps the actual sleep to 20 seconds max per retry.
  2. Adds a circuit breaker: the first time Groq asks for a wait longer than
     that, it's treated as "daily quota exhausted" rather than a transient
     throttle — Groq is skipped for the rest of that job's run, and every
     subsequent comparison goes straight to Gemini instead of repeating the
     same multi-minute wait.

This mirrors the exact fix already validated in migrate_content_generator.py.

USAGE:
    Save this file in the ROOT of your opensource-alternative-finder repo,
    then run:

        python3 fix_groq_uncapped_sleep.py

Safe to re-run — skips if already applied.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET = "scripts/generate_comparison.py"

MARKER = "GROQ_QUOTA_EXHAUSTED"

DEFINE_OLD = """def generate_with_groq(prompt: str, retries: int = 2) -> str:
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
            if attempt < retries:"""

DEFINE_NEW = """GROQ_QUOTA_EXHAUSTED = False  # set once we see a long retry-after — see generate_with_groq
GROQ_MAX_SLEEP = 20  # never actually sleep longer than this for a single retry, regardless of what the API asks for


class GroqQuotaExhausted(Exception):
    \"\"\"Raised when Groq's retry-after suggests the daily quota is spent, not a
    transient per-minute throttle. Sleeping through a multi-minute wait here is
    what caused this pipeline to run for over an hour on a single batch. Once
    we see this, we stop calling Groq for the rest of the run and go straight
    to Gemini instead of repeating the same wait per pair.\"\"\"
    pass


def generate_with_groq(prompt: str, retries: int = 2) -> str:
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
            if response.status_code == 429:
                wait = int(response.headers.get('retry-after', 15))
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
            if attempt < retries:"""

CALLSITE_OLD = """def generate_comparison(prop_key: str, oss_key: str) -> Dict:
    prompt        = build_prompt(prop_key, oss_key)
    prop          = TOOLS.get(prop_key, {})
    alt           = TOOLS.get(oss_key,  {})
    content       = None
    provider_used = None

    try:
        content = generate_with_groq(prompt)
        provider_used = 'groq'
        logger.info(f"    Generated with Groq")
    except Exception as e:
        logger.warning(f"    Groq unavailable ({type(e).__name__}) -- trying Gemini...")
        time.sleep(2)"""

CALLSITE_NEW = """def generate_comparison(prop_key: str, oss_key: str) -> Dict:
    global GROQ_QUOTA_EXHAUSTED
    prompt        = build_prompt(prop_key, oss_key)
    prop          = TOOLS.get(prop_key, {})
    alt           = TOOLS.get(oss_key,  {})
    content       = None
    provider_used = None

    if not GROQ_QUOTA_EXHAUSTED:
        try:
            content = generate_with_groq(prompt)
            provider_used = 'groq'
            logger.info(f"    Generated with Groq")
        except GroqQuotaExhausted as e:
            logger.warning(f"    {e}")
            GROQ_QUOTA_EXHAUSTED = True
        except Exception as e:
            logger.warning(f"    Groq unavailable ({type(e).__name__}) -- trying Gemini...")
            time.sleep(2)"""


def main():
    path = os.path.join(ROOT, TARGET)
    if not os.path.exists(path):
        print(f"ERROR: {TARGET} not found. Run this from the repo root.")
        sys.exit(1)

    with open(path) as f:
        src = f.read()

    if MARKER in src:
        print(f"SKIP: {TARGET} already patched.")
        return

    for label, old, new in [
        ("Groq retry cap + circuit breaker (function definition)", DEFINE_OLD, DEFINE_NEW),
        ("generate_comparison() circuit-breaker check", CALLSITE_OLD, CALLSITE_NEW),
    ]:
        if old not in src:
            print(f"ERROR: could not find the expected '{label}' block. Your file may differ "
                  f"from what this patch expects — no changes written. Check manually.")
            sys.exit(1)
        src = src.replace(old, new)
        print(f"Patched: {label}")

    with open(path, "w") as f:
        f.write(src)

    print(f"\nDone. {TARGET} will no longer sleep through multi-minute Groq rate limits.")
    print("Cancel the currently running pipeline workflow (if still running) and re-run it after this is applied.")


if __name__ == "__main__":
    main()
