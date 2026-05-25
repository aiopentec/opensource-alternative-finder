#!/usr/bin/env python3
"""
apply_publish_date_patch.py
─────────────────────────────────────────────────────────────────────────────
Patches publish_github_pages.py so each comparison page shows its own
staggered publish date (from the comparison JSON) instead of today's date.

Run from your repo root:
    python apply_publish_date_patch.py
─────────────────────────────────────────────────────────────────────────────
"""

import sys
from pathlib import Path

TARGET = Path("scripts/publish_github_pages.py")


def patch():
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found. Run from your repo root.")
        sys.exit(1)

    original = TARGET.read_text(encoding="utf-8")

    if "page_updated = comp.get('publish_date'" in original:
        print("Already patched. No changes made.")
        sys.exit(0)

    # ── Patch: add page_updated variable before COMPARISON_PAGE.format() ────
    anchors = [
        "        page_html = COMPARISON_PAGE.format(",
        "        page_html = COMPARISON_PAGE.format\n",
    ]
    anchor = next((a for a in anchors if a in original), None)

    if not anchor:
        print("ERROR: Could not find 'page_html = COMPARISON_PAGE.format(' in the file.")
        print("The publish_github_pages.py structure may have changed.")
        sys.exit(1)

    insert = "        page_updated = comp.get('publish_date', updated)\n"
    patched = original.replace(anchor, insert + anchor, 1)
    print("Step 1: page_updated variable added before COMPARISON_PAGE.format()")

    # ── Patch: replace updated=updated with updated=page_updated ────────────
    # The format() call passes updated= — we need to find that specific arg
    old_arg = "updated=updated,"
    new_arg = "updated=page_updated,"

    if old_arg not in patched:
        # Try alternate spacing
        old_arg = "            updated=updated,"
        new_arg = "            updated=page_updated,"

    if old_arg in patched:
        # Only replace the FIRST occurrence (inside COMPARISON_PAGE.format)
        patched = patched.replace(old_arg, new_arg, 1)
        print("Step 2: updated=updated changed to updated=page_updated")
    else:
        print("WARNING: Could not find updated=updated in format() call.")
        print("  The page_updated variable was added but not wired in.")
        print("  Manually change 'updated=updated' to 'updated=page_updated'")
        print("  inside the COMPARISON_PAGE.format() call.")

    TARGET.write_text(patched, encoding="utf-8")
    print(f"\nPatch complete. {TARGET} updated.")
    print("\nNext steps:")
    print("  git add scripts/publish_github_pages.py")
    print("  git commit -m 'Use per-page publish_date in comparison pages'")
    print("  git push")
    print("  Then trigger pipeline: Actions -> publish mode")


if __name__ == "__main__":
    patch()
