#!/usr/bin/env python3
"""
thin_content_audit.py
Audits migrate-*/index.html AND {tool}-vs-{tool}/index.html comparison
pages for thin content (Google AdSense's ~200 unique-word threshold).
Strips shared boilerplate (nav, footer, scripts, styles) so the word
count reflects content that's actually unique to each page, not repeated
site-wide chrome.

The comparison-page check exists because generate_comparison.py can, in
rare cases, accept an empty/near-empty AI response and still mark it
'generated' — this audit is the last line of defense that catches a
resulting blank page before it deploys, independent of whether the
generation-side fix is in place.

USAGE:
    # Audit a locally built site/ folder (default)
    python3 scripts/thin_content_audit.py

    # Audit a different folder
    python3 scripts/thin_content_audit.py --dir site

    # Change the thin-content threshold (default 200, matches AdSense)
    python3 scripts/thin_content_audit.py --threshold 200

    # Write a CSV report instead of printing a table
    python3 scripts/thin_content_audit.py --csv data/audit_report.csv

Exit code is 1 if any page is below the threshold (useful in CI to block
a deploy or fail a workflow step before submitting for AdSense review),
0 if every page passes.
"""
import argparse
import csv
import glob
import os
import re
import sys

# Basic named-entity decode table — enough for what these pages emit.
ENTITIES = {
    "&amp;": "&", "&nbsp;": " ", "&lt;": "<", "&gt;": ">",
    "&quot;": '"', "&#39;": "'", "&mdash;": "—", "&ndash;": "–",
    "&rsquo;": "'", "&lsquo;": "'", "&rdquo;": '"', "&ldquo;": '"',
}


def strip_html(html: str) -> str:
    # Drop whole blocks that are boilerplate / non-content first.
    html = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<style\b[^>]*>.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<nav\b[^>]*>.*?</nav>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<footer\b[^>]*>.*?</footer>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    # Strip remaining tags.
    text = re.sub(r"<[^>]+>", " ", html)
    for ent, ch in ENTITIES.items():
        text = text.replace(ent, ch)
    text = re.sub(r"&#\d+;", " ", text)  # any remaining numeric entities
    return text


def word_count(text: str) -> int:
    words = re.findall(r"[A-Za-z0-9'-]+", text)
    return len(words)


def audit(site_dir: str, threshold: int, comparison_threshold: int = None):
    # Comparison pages carry more surrounding template furniture (difficulty
    # card, verdict box, GitHub box, pricing header) than migrate pages do,
    # so a blank comparison_markdown still clears a 200-word bar — they need
    # a higher threshold to actually catch an empty AI response. Calibrated
    # against real data: broken comparison pages topped out at 331 words,
    # genuinely-content comparison pages started at 488.
    if comparison_threshold is None:
        comparison_threshold = threshold

    migrate_files    = sorted(glob.glob(os.path.join(site_dir, "migrate-*", "index.html")))
    comparison_files = sorted(glob.glob(os.path.join(site_dir, "*-vs-*", "index.html")))
    if not migrate_files and not comparison_files:
        print(f"No migrate-*/index.html or *-vs-*/index.html files found under {site_dir}/")
        print("Did you run the build first? e.g. python3 scripts/publish_github_pages.py")
        sys.exit(2)

    results = []
    for path, page_threshold in (
        [(p, threshold) for p in migrate_files] +
        [(p, comparison_threshold) for p in comparison_files]
    ):
        slug = os.path.basename(os.path.dirname(path))
        with open(path, encoding="utf-8") as f:
            html = f.read()
        text = strip_html(html)
        wc = word_count(text)
        results.append({"slug": slug, "word_count": wc, "thin": wc < page_threshold, "threshold_used": page_threshold})

    results.sort(key=lambda r: r["word_count"])
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="site", help="Site output folder (default: site)")
    ap.add_argument("--threshold", type=int, default=200, help="Thin-content word threshold for migrate-* pages (default: 200)")
    ap.add_argument("--comparison-threshold", type=int, default=400, help="Thin-content word threshold for *-vs-* comparison pages (default: 400 — these carry more template furniture than migrate pages, so a blank comparison_markdown can still clear 200)")
    ap.add_argument("--csv", default=None, help="Optional path to write a CSV report")
    args = ap.parse_args()

    results = audit(args.dir, args.threshold, args.comparison_threshold)

    thin = [r for r in results if r["thin"]]
    ok = [r for r in results if not r["thin"]]
    counts = [r["word_count"] for r in results]
    median = sorted(counts)[len(counts) // 2] if counts else 0

    print(f"\n{'slug':<45} {'words':>7}  status")
    print("-" * 65)
    for r in results:
        status = "THIN" if r["thin"] else "ok"
        print(f"{r['slug']:<45} {r['word_count']:>7}  {status}")

    print("-" * 65)
    print(f"Total pages:      {len(results)}")
    print(f"Thin (migrate < {args.threshold}, comparison < {args.comparison_threshold}): {len(thin)}")
    print(f"OK:               {len(ok)}")
    print(f"Median words:     {median}")

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["slug", "word_count", "thin", "threshold_used"])
            w.writeheader()
            w.writerows(results)
        print(f"\nCSV written to {args.csv}")

    sys.exit(1 if thin else 0)


if __name__ == "__main__":
    main()
