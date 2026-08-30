#!/usr/bin/env python3
"""
fix_empty_comparison_content.py
generate_with_groq() returns whatever the API gives back with no validation.
If Groq responds with only the trailing meta-JSON block and no actual
comparison essay, strip_meta_block() correctly strips it down to nothing —
but generate_comparison() still marks status: 'generated' and ships the
empty result. This isn't hypothetical: it happened for real, live, to 4 of
63 comparisons (jira-vs-plane, mailchimp-vs-listmonk, openai-api-vs-ollama,
quickbooks-vs-dolibarr), and since generate_comparison.py regenerates every
pair unconditionally each day, it reproduced the same empty result on the
next run too.

This patch validates content (post meta-stripping) after each tier in the
waterfall. If Groq's output is empty or too short, it's treated as a
failure and the code falls through to Gemini; if Gemini's output is also
too short, it falls through to the template engine — which always
produces ~800-900 words from the TOOLS/TEMPLATE_DETAILS data already in
the repo, so it's a safe, guaranteed-non-empty final tier. As a last
line of defense, the returned record's status is only set to 'generated'
if the final content actually clears the threshold; otherwise 'failed',
so a status check could catch it even if content validation somehow
doesn't.

Because generate_comparison.py regenerates all 63 pairs unconditionally
on every run, no separate backfill is needed — the next pipeline run
after this patch will naturally produce real content for the 4 currently-
empty pages.

USAGE:
    Save this file in the ROOT of your opensource-alternative-finder repo,
    then run:

        python3 fix_empty_comparison_content.py

Safe to re-run — skips if already applied.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET = "scripts/generate_comparison.py"

MARKER = "_content_is_valid"

# ── Edit 1: add the validation helper, right before generate_comparison() ──
HELPER_OLD = """def generate_comparison(prop_key: str, oss_key: str) -> Dict:"""

HELPER_NEW = """MIN_CONTENT_WORDS = 150


def _content_is_valid(raw_content: str) -> bool:
    \"\"\"True if raw_content, after stripping the trailing meta block, has
    enough real words to be a genuine comparison rather than an empty or
    metadata-only response.\"\"\"
    if not raw_content:
        return False
    cleaned = strip_meta_block(raw_content)
    return len(cleaned.split()) >= MIN_CONTENT_WORDS


def generate_comparison(prop_key: str, oss_key: str) -> Dict:"""

# ── Edit 2: validate Groq's output before accepting it ──────────────────────
GROQ_OLD = """    if not GROQ_QUOTA_EXHAUSTED:
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

GROQ_NEW = """    if not GROQ_QUOTA_EXHAUSTED:
        try:
            candidate = generate_with_groq(prompt)
            if _content_is_valid(candidate):
                content = candidate
                provider_used = 'groq'
                logger.info(f"    Generated with Groq")
            else:
                logger.warning(f"    Groq returned empty/too-short content -- trying Gemini...")
        except GroqQuotaExhausted as e:
            logger.warning(f"    {e}")
            GROQ_QUOTA_EXHAUSTED = True
        except Exception as e:
            logger.warning(f"    Groq unavailable ({type(e).__name__}) -- trying Gemini...")
            time.sleep(2)"""

# ── Edit 3: validate Gemini's output before accepting it ────────────────────
GEMINI_OLD = """    if content is None:
        try:
            content = generate_with_gemini(prompt)
            provider_used = 'gemini'
            logger.info(f"    Generated with Gemini")
        except Exception as e:
            logger.warning(f"    Gemini unavailable ({type(e).__name__}) -- using template...")"""

GEMINI_NEW = """    if content is None:
        try:
            candidate = generate_with_gemini(prompt)
            if _content_is_valid(candidate):
                content = candidate
                provider_used = 'gemini'
                logger.info(f"    Generated with Gemini")
            else:
                logger.warning(f"    Gemini returned empty/too-short content -- using template...")
        except Exception as e:
            logger.warning(f"    Gemini unavailable ({type(e).__name__}) -- using template...")"""

# ── Edit 4: status only says 'generated' if the final content really is ────
STATUS_OLD = """        'generated_at':        datetime.utcnow().isoformat() + 'Z',
        'status':              'generated'
    }"""

STATUS_NEW = """        'generated_at':        datetime.utcnow().isoformat() + 'Z',
        'status':              'generated' if len(clean_content.split()) >= MIN_CONTENT_WORDS else 'failed'
    }"""


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
        ("validation helper", HELPER_OLD, HELPER_NEW),
        ("validate Groq output", GROQ_OLD, GROQ_NEW),
        ("validate Gemini output", GEMINI_OLD, GEMINI_NEW),
        ("honest status field", STATUS_OLD, STATUS_NEW),
    ]:
        if src.count(old) != 1:
            print(f"ERROR: expected exactly one occurrence of '{label}' anchor, found "
                  f"{src.count(old)}. Your file may differ from what this patch expects "
                  f"— no changes written. Check manually.")
            sys.exit(1)
        src = src.replace(old, new)
        print(f"Patched: {label}")

    with open(path, "w") as f:
        f.write(src)

    print(f"\nDone. {TARGET} now validates content before accepting it from each "
          f"provider tier, and falls through to the next tier (ultimately the "
          f"template engine, which always produces real content) instead of "
          f"silently shipping empty pages.")
    print("The next full pipeline run will naturally regenerate real content for "
          "the 4 currently-empty comparisons — no separate backfill needed.")


if __name__ == "__main__":
    main()
