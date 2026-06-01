"""
add_ph_badge.py
───────────────
Patches publish_github_pages.py to show the ProductHunt badge in two places:
  1. Homepage hero — next to the "Star us on GitHub" button
  2. Homepage footer — alongside the other footer links

HOW TO USE
──────────
Step 1: Go to https://www.producthunt.com/products/open-source-alternative-finder/embed
        Copy the HTML embed code for the "neutral" or "featured" badge.
        It will look like:
        <a href="https://www.producthunt.com/posts/open-source-alternative-finder"...>
          <img src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=XXXXX...">
        </a>

Step 2: Paste the code into PH_BADGE_EMBED below (replace the placeholder).

Step 3: Run:  python add_ph_badge.py
        Then commit and push, or trigger the pipeline in publish mode.
"""

import sys
from pathlib import Path

TARGET = Path("scripts/publish_github_pages.py")

# ── PASTE YOUR PH EMBED CODE HERE ────────────────────────────────────────────
PH_BADGE_EMBED = """<a href="https://www.producthunt.com/products/open-source-alternative-finder?embed=true&amp;utm_source=badge-featured&amp;utm_medium=badge&amp;utm_campaign=badge-open-source-alternative-finder-2" target="_blank" rel="noopener noreferrer"><img alt="Open Source Alternative Finder - Free replacements for Slack, Notion, Figma &amp; 60+ paid tools | Product Hunt" width="250" height="54" src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=1159136&amp;theme=light&amp;t=1780308677291"></a>"""
# ─────────────────────────────────────────────────────────────────────────────

SENTINEL = "PH_BADGE_INJECTED"

# ── Hero badge: sits next to "Star us on GitHub" button ──────────────────────
HERO_OLD = """    <a href="https://github.com/aiopentec/opensource-alternative-finder" target="_blank" rel="noopener"
       style="display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,0.15);
              border:1px solid rgba(255,255,255,0.35);color:#fff;padding:6px 14px;
              border-radius:20px;font-size:12px;font-weight:600;text-decoration:none;">
      ⭐ Star us on GitHub
    </a>"""

HERO_NEW = """    <a href="https://github.com/aiopentec/opensource-alternative-finder" target="_blank" rel="noopener"
       style="display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,0.15);
              border:1px solid rgba(255,255,255,0.35);color:#fff;padding:6px 14px;
              border-radius:20px;font-size:12px;font-weight:600;text-decoration:none;">
      ⭐ Star us on GitHub
    </a>
    <div style="display:inline-flex;align-items:center;vertical-align:middle;margin-left:8px;">
      PH_BADGE_PLACEHOLDER
    </div>"""

# ── Footer badge: added before the closing </footer> tag in INDEX_PAGE ────────
FOOTER_OLD = """  <span style="font-size:0.8rem; opacity:0.7">Updated {updated} &nbsp;·&nbsp; $0/month to operate &nbsp;·&nbsp; AI-researched daily · Verify details before switching</span>
</footer>"""

FOOTER_NEW = """  <span style="font-size:0.8rem; opacity:0.7">Updated {updated} &nbsp;·&nbsp; $0/month to operate &nbsp;·&nbsp; AI-researched daily · Verify details before switching</span>
  <div style="margin-top:1rem;">PH_BADGE_PLACEHOLDER</div>
</footer>"""


def patch():
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found. Run from your repo root.")
        sys.exit(1)

    if "REPLACE_WITH_YOUR_POST_ID" in PH_BADGE_EMBED:
        print("ERROR: Replace REPLACE_WITH_YOUR_POST_ID in PH_BADGE_EMBED with your actual post ID.")
        print("       Find it in the embed code at:")
        print("       https://www.producthunt.com/products/open-source-alternative-finder/embed")
        sys.exit(1)

    content = TARGET.read_text(encoding="utf-8")

    if SENTINEL in content:
        print("Already patched. No changes made.")
        sys.exit(0)

    badge_oneline = PH_BADGE_EMBED.replace("\n", " ").strip()
    hero_new_final   = HERO_NEW.replace("PH_BADGE_PLACEHOLDER", badge_oneline)
    footer_new_final = FOOTER_NEW.replace("PH_BADGE_PLACEHOLDER", badge_oneline)

    changed = False

    if HERO_OLD in content:
        content = content.replace(HERO_OLD, hero_new_final, 1)
        print("Step 1: PH badge added to homepage hero ✅")
        changed = True
    else:
        print("Step 1: Could not find hero GitHub button — hero badge skipped.")

    if FOOTER_OLD in content:
        content = content.replace(FOOTER_OLD, footer_new_final, 1)
        print("Step 2: PH badge added to homepage footer ✅")
        changed = True
    else:
        print("Step 2: Could not find footer anchor — footer badge skipped.")

    if changed:
        content = content.replace(
            "# ── CONFIG — edit these ───",
            f"# {SENTINEL}\n# ── CONFIG — edit these ───",
            1
        )
        TARGET.write_text(content, encoding="utf-8")
        print(f"\nPatch complete. {TARGET} updated.")
        print("Trigger the pipeline in publish mode to deploy.")
    else:
        print("\nNo changes applied — check anchor strings above.")


if __name__ == "__main__":
    patch()
