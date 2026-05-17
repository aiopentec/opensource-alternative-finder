#!/usr/bin/env python3
"""
add_vps_blocks.py
─────────────────────────────────────────────────────────────────────────────
Automatically patches scripts/publish_github_pages.py to add VPS affiliate
blocks to all self-hostable comparison pages.

Run from your repo root:
    python add_vps_blocks.py

Then commit and push the result.
─────────────────────────────────────────────────────────────────────────────
"""

import sys
from pathlib import Path

TARGET = Path("scripts/publish_github_pages.py")

# ── The clean function to insert ──────────────────────────────────────────────
# Uses .join() and format() instead of f-strings to avoid quote conflicts.

NEW_FUNCTION = r"""

def build_vps_block(oss_key, oss_name):
    VPS_TOOLS = {
        "mattermost": ("$6/mo",  "handles up to 100 users comfortably"),
        "element":    ("$12/mo", "needs 2GB RAM for Element + Synapse"),
        "zulip":      ("$12/mo", "Zulip recommends 2GB RAM minimum"),
        "gitlab":     ("$24/mo", "GitLab needs 4GB RAM for CI/CD pipelines"),
        "gitea":      ("$6/mo",  "extremely lightweight, runs on minimal hardware"),
        "penpot":     ("$12/mo", "Docker Compose setup needs 2GB RAM"),
        "plane":      ("$6/mo",  "very lightweight self-host"),
        "wekan":      ("$6/mo",  "runs fine on the smallest server"),
        "nextcloud":  ("$12/mo", "AIO installer needs at least 2GB RAM"),
        "jitsi":      ("$12/mo", "video conferencing needs more RAM for concurrent calls"),
        "taiga":      ("$12/mo", "multi-container setup needs 2GB+"),
        "nocodb":     ("$6/mo",  "single container, almost zero resource usage"),
        "listmonk":   ("$6/mo",  "single binary, minimal resource usage"),
        "ghost":      ("$6/mo",  "lightweight and well-optimised"),
        "suitecrm":   ("$12/mo", "LAMP stack needs 2GB+ RAM"),
    }
    if oss_key not in VPS_TOOLS:
        return ""
    cost, note = VPS_TOOLS[oss_key]
    DO_LINK    = "https://m.do.co/c/e4316dc73fa1"
    VULTR_LINK = "https://www.vultr.com/?ref=9901332"
    parts = [
        '<div style="background:#f0fdf4;border:1px solid #bbf7d0;'
        'border-radius:12px;padding:1.25rem 1.5rem;margin-bottom:1.5rem;">',
        '<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.1em;color:#16a34a;margin-bottom:0.5rem;">'
        '\U0001f5a5\ufe0f Ready to self-host {name}?</div>'.format(name=oss_name),
        '<p style="font-size:0.88rem;color:#374151;margin-bottom:0.75rem;line-height:1.6;">'
        'A <strong>{cost} server</strong> {note}. No per-seat fees, ever.</p>'.format(
            cost=cost, note=note),
        '<div style="display:flex;gap:0.6rem;flex-wrap:wrap;margin-bottom:0.6rem;">',
        '<a href="{do}" target="_blank" rel="noopener sponsored"'
        ' style="background:#0080ff;color:#fff;padding:0.5rem 1rem;'
        'border-radius:7px;text-decoration:none;font-weight:700;font-size:0.82rem;">'
        'DigitalOcean \u2014 $200 free credit \u2192</a>'.format(do=DO_LINK),
        ' <a href="{vultr}" target="_blank" rel="noopener sponsored"'
        ' style="background:#fff;color:#007bfc;border:2px solid #007bfc;'
        'padding:0.5rem 1rem;border-radius:7px;text-decoration:none;'
        'font-weight:700;font-size:0.82rem;">'
        'Vultr \u2014 $300 free credit \u2192</a>'.format(vultr=VULTR_LINK),
        '</div>',
        '<p style="font-size:0.72rem;color:#9ca3af;margin:0;">'
        'Affiliate links \u2014 we earn a small commission at no cost to you.</p>',
        '</div>',
    ]
    return "".join(parts)

"""


def find_anchor(text, candidates):
    for c in candidates:
        if c in text:
            return c
    return None


def patch_file():
    # ── Verify file exists ────────────────────────────────────────────────────
    if not TARGET.exists():
        print(f"\n❌  File not found: {TARGET}")
        print("    Run this script from your repo root.")
        print("    Example:  cd opensource-alternative-finder")
        print("              python add_vps_blocks.py")
        sys.exit(1)

    original = TARGET.read_text(encoding="utf-8")
    patched  = original

    # ── Guard against double-patching ─────────────────────────────────────────
    if "def build_vps_block(" in original:
        print("⚠️   build_vps_block() already exists in the file.")
        # Still check if wiring is missing
        if "{vps_block}" not in original:
            print("     The function exists but is not wired into the template.")
            print("     Continuing to add wiring only...")
        else:
            print("     File is already fully patched. No changes made.")
            sys.exit(0)

    # ────────────────────────────────────────────────────────────────────────────
    # PATCH 1 — Insert the function
    # ────────────────────────────────────────────────────────────────────────────
    if "def build_vps_block(" not in patched:
        anchors = [
            "def build_difficulty_card(",
            "def build_verdict_box(",
            "def build_related_section(",
            "def build_sitemap(",
            "DIFFICULTY_COLORS = {",
        ]
        anchor = find_anchor(patched, anchors)
        if anchor:
            patched = patched.replace(anchor, NEW_FUNCTION + "\n" + anchor, 1)
            print("✅  Patch 1: build_vps_block() function added")
        else:
            print("❌  Patch 1 FAILED: Could not find insertion point.")
            print("    Please share the file and we'll fix it manually.")
            sys.exit(1)

    # ────────────────────────────────────────────────────────────────────────────
    # PATCH 2 — Add vps_block_html variable before migration_link_html
    # ────────────────────────────────────────────────────────────────────────────
    if "vps_block_html = build_vps_block(" not in patched:
        anchors = [
            "        migration_link_html = f\"\"\"",
            "        migration_link_html = f'''",
            "        migration_link_html =",
        ]
        anchor = find_anchor(patched, anchors)
        if anchor:
            insert = "        vps_block_html = build_vps_block(oss_key, oss_name)\n"
            patched = patched.replace(anchor, insert + anchor, 1)
            print("✅  Patch 2: vps_block_html variable added")
        else:
            print("⚠️   Patch 2 SKIPPED: Could not find migration_link_html.")
            print("    Add manually: vps_block_html = build_vps_block(oss_key, oss_name)")

    # ────────────────────────────────────────────────────────────────────────────
    # PATCH 3 — Add vps_block= to COMPARISON_PAGE.format() call
    # ────────────────────────────────────────────────────────────────────────────
    if "vps_block=vps_block_html," not in patched:
        anchors = [
            "            migration_link=migration_link_html,",
            "            migration_link = migration_link_html,",
        ]
        anchor = find_anchor(patched, anchors)
        if anchor:
            patched = patched.replace(
                anchor,
                anchor + "\n            vps_block=vps_block_html,",
                1
            )
            print("✅  Patch 3: vps_block= added to COMPARISON_PAGE.format()")
        else:
            print("⚠️   Patch 3 SKIPPED: Could not find migration_link= in format() call.")
            print("    Add manually: vps_block=vps_block_html,")

    # ────────────────────────────────────────────────────────────────────────────
    # PATCH 4 — Add {vps_block} to the COMPARISON_PAGE template string
    # ────────────────────────────────────────────────────────────────────────────
    if "{vps_block}" not in patched:
        anchors = [
            "  {migration_link}\n",
            "{migration_link}\n",
        ]
        anchor = find_anchor(patched, anchors)
        if anchor:
            patched = patched.replace(
                anchor,
                anchor + "  {vps_block}\n",
                1
            )
            print("✅  Patch 4: {vps_block} placeholder added to template")
        else:
            print("⚠️   Patch 4 SKIPPED: Could not find {migration_link} in template.")
            print("    Add {vps_block} after {migration_link} in COMPARISON_PAGE.")

    # ────────────────────────────────────────────────────────────────────────────
    # Write result
    # ────────────────────────────────────────────────────────────────────────────
    if patched == original:
        print("\n⚠️   No changes were made. The file may already be patched")
        print("    or the anchors could not be found.")
        sys.exit(0)

    TARGET.write_text(patched, encoding="utf-8")

    print(f"\n✅  Done. {TARGET} has been patched successfully.")
    print("\nNext steps:")
    print("  1. Verify the file looks correct:")
    print("     python -c \"import scripts.publish_github_pages\"")
    print("     (no output = no syntax errors)")
    print()
    print("  2. Commit and push:")
    print("     git add scripts/publish_github_pages.py")
    print("     git commit -m 'Add VPS affiliate blocks to self-hosting pages'")
    print("     git push")
    print()
    print("  3. Trigger pipeline: Actions → Run workflow → mode: publish")


if __name__ == "__main__":
    patch_file()
