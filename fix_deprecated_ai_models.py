#!/usr/bin/env python3
"""
fix_deprecated_ai_models.py
Your daily pipeline's AI content generation has been silently broken since
August 18, 2026 — Groq deprecated llama-3.3-70b-versatile (shutdown Aug 16)
and Gemini's gemini-1.5-flash has been fully decommissioned (returns 404
on every request). Both failures are caught by generate_comparison.py's
try/except waterfall, so no error surfaced — it just quietly fell through
to the template-only generator. Checked your data/cache/comparisons_*.json:
every one of the last 2 daily runs (Aug 18, Aug 19) generated with
provider="template" instead of AI-written content.

This patches scripts/generate_comparison.py to use current, supported
models:
  Groq:   llama-3.3-70b-versatile  -->  openai/gpt-oss-120b
          (Groq's own recommended replacement)
  Gemini: gemini-1.5-flash         -->  gemini-2.5-flash-lite
          (Google's current free-tier workhorse model, no shutdown
          date announced as of Aug 2026)

USAGE:
    Save this file in the ROOT of your opensource-alternative-finder repo
    (same folder as scripts/), then run:

        python3 fix_deprecated_ai_models.py

Safe to re-run — checks for the new model strings before patching and
skips if already applied.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET = "scripts/generate_comparison.py"

GROQ_OLD = "            'model': 'llama-3.3-70b-versatile',"
GROQ_NEW = "            'model': 'openai/gpt-oss-120b',"

GEMINI_OLD = "        f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}',"
GEMINI_NEW = "        f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}',"


def main():
    path = os.path.join(ROOT, TARGET)
    if not os.path.exists(path):
        print(f"ERROR: {TARGET} not found. Run this from the repo root.")
        sys.exit(1)

    with open(path) as f:
        src = f.read()

    if "openai/gpt-oss-120b" in src and "gemini-2.5-flash-lite" in src:
        print(f"SKIP: {TARGET} already patched.")
        return

    changed = False
    for label, old, new in [
        ("Groq model (llama-3.3-70b-versatile -> openai/gpt-oss-120b)", GROQ_OLD, GROQ_NEW),
        ("Gemini model (gemini-1.5-flash -> gemini-2.5-flash-lite)", GEMINI_OLD, GEMINI_NEW),
    ]:
        if old not in src:
            print(f"WARNING: could not find expected '{label}' text — skipping this one. "
                  f"Your file may already differ from what this patch expects.")
            continue
        src = src.replace(old, new)
        print(f"Patched: {label}")
        changed = True

    if not changed:
        print("Nothing was patched — no matching text found.")
        sys.exit(1)

    with open(path, "w") as f:
        f.write(src)

    print(f"\nDone. {TARGET} now uses current, supported models.")
    print("Your next pipeline run should show provider=\"groq\" again in data/cache/comparisons_*.json")
    print("instead of provider=\"template\".")


if __name__ == "__main__":
    main()
