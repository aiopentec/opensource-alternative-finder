#!/usr/bin/env python3
"""
fix_datemodified_freshness.py
Every comparison page's schema.org "dateModified" is currently stamped with
the exact pipeline-run timestamp (iso_date, computed once at the top of
build_site() and reused for all 57+ comparison pages), regardless of whether
that comparison's actual facts changed. That means every page claims to have
been "modified" today, every single day, even when nothing about it is
different from yesterday.

This patch adds real per-comparison freshness tracking:
  - A fingerprint is computed per comparison from the fields that would
    actually reflect a real-world change (pricing, GitHub stars, website
    URLs).
  - A persisted state file (data/cache/freshness_state.json) stores each
    slug's last fingerprint and the date it last changed.
  - dateModified for a comparison page only advances to today if that
    comparison's fingerprint differs from what was last stored — otherwise
    it keeps showing the date it was last actually verified as changed.
  - data/cache/ is already committed back to the repo by the existing
    "Cache comparison data to repo" step in pipeline.yml (it does
    `git add data/cache/`, not just comparisons_*.json), so no workflow
    changes are needed — freshness_state.json rides along automatically.

This only touches the per-comparison Article dateModified (the highest-
volume page type: one per comparison). The four other inline
datetime.utcnow() stamps (stats page, blog posts, industry pages,
price-hike page) have the same issue but are lower-volume and are
deliberately left alone here to keep this change small and reviewable —
same pattern can be applied to them later if useful.

USAGE:
    Save this file in the ROOT of your opensource-alternative-finder repo,
    then run:

        python3 fix_datemodified_freshness.py

Safe to re-run — skips if already applied.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET = "scripts/publish_github_pages.py"

MARKER = "freshness_state"

# ── Edit 1: load freshness state + add the helper function ──────────────────
LOAD_OLD = """    logger.info(f"📦 Building site from {len(all_comparisons)} comparisons...")
    updated   = datetime.utcnow().strftime('%B %d, %Y')
    iso_date  = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')"""

LOAD_NEW = """    logger.info(f"📦 Building site from {len(all_comparisons)} comparisons...")
    updated   = datetime.utcnow().strftime('%B %d, %Y')
    iso_date  = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    # ── Per-comparison freshness tracking ────────────────────────────────
    # dateModified should only advance when a comparison's actual facts
    # change, not on every pipeline run. State persists in data/cache/,
    # which the pipeline already commits back to the repo.
    freshness_state_path = Path('data/cache/freshness_state.json')
    if freshness_state_path.exists():
        with open(freshness_state_path) as f:
            freshness_state = json.load(f)
    else:
        freshness_state = {}

    def get_last_verified(comp: Dict) -> str:
        slug = comp.get('slug', '')
        fingerprint = '|'.join([
            str(comp.get('proprietary_pricing', '')),
            str(comp.get('oss_pricing', '')),
            str(comp.get('oss_stars', '')),
            str(comp.get('oss_website', '')),
            str(comp.get('proprietary_website', '')),
        ])
        prev = freshness_state.get(slug)
        if prev and prev.get('fingerprint') == fingerprint:
            last_verified = prev.get('last_verified', iso_date)
        else:
            last_verified = iso_date
        freshness_state[slug] = {'fingerprint': fingerprint, 'last_verified': last_verified}
        return last_verified"""

# ── Edit 2: use it at the comparison-page callsite ───────────────────────────
CALLSITE_OLD = """        page_html = COMPARISON_PAGE.format(
            title=comp['title'],
            seo_title=seo_title,
            seo_description=seo_desc,
            canonical_url=canonical,
            site_base_url=SITE_BASE_URL,
            iso_date=iso_date,"""

CALLSITE_NEW = """        last_verified = get_last_verified(comp)

        page_html = COMPARISON_PAGE.format(
            title=comp['title'],
            seo_title=seo_title,
            seo_description=seo_desc,
            canonical_url=canonical,
            site_base_url=SITE_BASE_URL,
            iso_date=last_verified,"""

# ── Edit 3: persist state after the comparison loop finishes ────────────────
SAVE_OLD = """    # Category index pages
    for category in categories:"""

SAVE_NEW = """    freshness_state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(freshness_state_path, 'w') as f:
        json.dump(freshness_state, f, indent=2)

    # Category index pages
    for category in categories:"""


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
        ("load freshness state + helper function", LOAD_OLD, LOAD_NEW),
        ("comparison-page callsite", CALLSITE_OLD, CALLSITE_NEW),
        ("persist state after comparison loop", SAVE_OLD, SAVE_NEW),
    ]:
        if old not in src:
            print(f"ERROR: could not find the expected '{label}' block. Your file may "
                  f"differ from what this patch expects — no changes written. Check manually.")
            sys.exit(1)
        src = src.replace(old, new)
        print(f"Patched: {label}")

    with open(path, "w") as f:
        f.write(src)

    print(f"\nDone. {TARGET} now tracks real per-comparison freshness in "
          f"data/cache/freshness_state.json.")
    print("First run after this patch will set every slug's last_verified to today "
          "(nothing to compare against yet) — dates will only start diverging from "
          "there once a comparison's facts actually change on a later run.")


if __name__ == "__main__":
    main()
