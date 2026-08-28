#!/usr/bin/env python3
"""
add_llms_txt.py
Adds an /llms.txt file to the built site, right alongside the existing
robots.txt write. robots.txt already allows all crawlers (User-agent: *,
Allow: /) so AI crawlers were never blocked — this doesn't change access,
it gives AI systems reading the site a short, direct description of what
it is and where the structured data lives, instead of making them infer
it from the HTML.

Content is generated dynamically from the same all_comparisons/categories
variables already in scope inside build_site(), so the comparison count
stays accurate on every rebuild without extra maintenance.

USAGE:
    Save this file in the ROOT of your opensource-alternative-finder repo,
    then run:

        python3 add_llms_txt.py

Safe to re-run — skips if already applied.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET = "scripts/publish_github_pages.py"

MARKER = "llms.txt"

OLD = """    with open(Path(site_dir) / 'robots.txt', 'w') as f:
        f.write(f"User-agent: *\\nAllow: /\\nSitemap: {SITE_BASE_URL}/sitemap.xml\\n")
    with open(Path(site_dir) / 'ads.txt', 'w') as f:"""

NEW = """    with open(Path(site_dir) / 'robots.txt', 'w') as f:
        f.write(f"User-agent: *\\nAllow: /\\nSitemap: {SITE_BASE_URL}/sitemap.xml\\n")
    llms_txt = f\"\"\"# Open Source Alternative Finder

> Comparison data for {len(all_comparisons)} proprietary SaaS tools against verified \\
open-source alternatives: pricing, self-hosting difficulty, migration steps, and licensing.

Every comparison page includes a pricing table, a self-hosting difficulty rating, \\
step-by-step migration steps, and an FAQ. Structured data (schema.org Article, \\
SoftwareApplication, FAQPage, HowTo) is embedded on every page.

## Data
- Full dataset (JSON, all {len(all_comparisons)} comparisons): {SITE_BASE_URL}/data/comparisons.json
- Pricing/adoption statistics: {SITE_BASE_URL}/stats/

## Key pages
- Home / full comparison index: {SITE_BASE_URL}/
- About this project, methodology, and how content is generated: {SITE_BASE_URL}/about/
- Categories: {', '.join(sorted(categories))}

## Notes for automated systems
Pricing figures are scraped from official sources and AI-summarized; they may lag \\
behind recent vendor changes. Always verify current pricing at the vendor's own site \\
before citing a specific number. Full pipeline source: https://github.com/aiopentec/opensource-alternative-finder
\"\"\"
    with open(Path(site_dir) / 'llms.txt', 'w') as f:
        f.write(llms_txt)
    with open(Path(site_dir) / 'ads.txt', 'w') as f:"""


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

    if OLD not in src:
        print("ERROR: could not find the expected robots.txt block. Your file may "
              "differ from what this patch expects — no changes written. Check manually.")
        sys.exit(1)

    src = src.replace(OLD, NEW)

    with open(path, "w") as f:
        f.write(src)

    print(f"Patched: {TARGET}")
    print("Done. The next site build will include /llms.txt.")


if __name__ == "__main__":
    main()
