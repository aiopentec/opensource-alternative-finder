#!/usr/bin/env python3
"""
vps_patch.py
─────────────────────────────────────────────────────────────────────────────
Adds a VPS hosting affiliate block to every self-hostable comparison page.
This is the highest-value affiliate opportunity on the site — natural intent,
zero friction.

HOW TO USE:
  1. Copy the build_vps_block() function into publish_github_pages.py
     (paste it after the existing build_primary_cta() function, around line 195)

  2. Replace YOUR_DO_LINK, YOUR_VULTR_LINK, YOUR_LINODE_LINK with your
     actual affiliate links after signing up at:
       DigitalOcean: https://www.digitalocean.com/referral-program
       Vultr:        https://www.vultr.com/referral-program/
       Linode/Akamai:https://www.linode.com/lp/referral/

  3. In the build_site() function, find the line that builds migration_link_html
     (around line 1150) and add {vps_block} to the template.

  4. Add the vps_block variable to each comparison page build loop.
─────────────────────────────────────────────────────────────────────────────
"""

# ── STEP 1: Add this function to publish_github_pages.py ─────────────────────
# Paste after build_primary_cta() function

VPS_AFFILIATE_LINKS = {
    "digitalocean": "YOUR_DO_AFFILIATE_LINK",       # Replace with your DO link
    "vultr":        "YOUR_VULTR_AFFILIATE_LINK",     # Replace with your Vultr link
    "linode":       "YOUR_LINODE_AFFILIATE_LINK",    # Replace with your Linode link
}

VPS_SETUP_COST = {
    # oss_key: (recommended_plan, monthly_cost, note)
    "mattermost": ("$6/mo Droplet",  "$6",  "handles up to 100 users comfortably"),
    "element":    ("$12/mo Droplet", "$12", "Element + Synapse needs 2GB+ RAM"),
    "zulip":      ("$12/mo Droplet", "$12", "Zulip recommends 2GB RAM minimum"),
    "gitlab":     ("$24/mo Droplet", "$24", "GitLab needs 4GB RAM — worth it for CI/CD"),
    "gitea":      ("$6/mo Droplet",  "$6",  "Gitea is extremely lightweight — runs on minimal hardware"),
    "penpot":     ("$12/mo Droplet", "$12", "Docker Compose setup needs 2GB RAM"),
    "plane":      ("$6/mo Droplet",  "$6",  "Plane self-host is very lightweight"),
    "wekan":      ("$6/mo Droplet",  "$6",  "WeKan runs fine on the smallest Droplet"),
    "nextcloud":  ("$12/mo Droplet", "$12", "Nextcloud with AIO needs at least 2GB"),
    "jitsi":      ("$12/mo Droplet", "$12", "Video requires more RAM for concurrent calls"),
    "taiga":      ("$12/mo Droplet", "$12", "Multi-container setup needs 2GB+"),
    "nocodb":     ("$6/mo Droplet",  "$6",  "NocoDB is single-container — very cheap to run"),
    "suitecrm":   ("$12/mo Droplet", "$12", "SuiteCRM with LAMP stack needs 2GB+"),
    "listmonk":   ("$6/mo Droplet",  "$6",  "Single binary — almost zero resource usage"),
    "ghost":      ("$6/mo Droplet",  "$6",  "Ghost is lightweight and well-optimised"),
}


def build_vps_block(oss_key: str, oss_name: str) -> str:
    """
    Returns the VPS hosting affiliate block HTML for self-hostable tools.
    Returns empty string for tools that don't benefit from VPS recommendations.
    """
    if oss_key not in VPS_SETUP_COST:
        return ""

    plan, cost, note = VPS_SETUP_COST[oss_key]
    do_link     = VPS_AFFILIATE_LINKS["digitalocean"]
    vultr_link  = VPS_AFFILIATE_LINKS["vultr"]

    return f"""
  <div style="background:#fff;border:1px solid #E2E8F0;border-radius:14px;
              padding:1.5rem 1.75rem;margin-bottom:1.5rem;
              box-shadow:0 2px 8px rgba(0,0,0,0.06);">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:1rem;">
      <span style="font-size:1.4rem;">🖥️</span>
      <div>
        <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;
                    letter-spacing:0.1em;color:#718096;margin-bottom:2px;">
          Ready to Self-Host {oss_name}?
        </div>
        <div style="font-size:1rem;font-weight:800;color:#1A202C;">
          Get a server in under 60 seconds
        </div>
      </div>
    </div>
    <p style="font-size:0.88rem;color:#4A5568;margin-bottom:1rem;line-height:1.6;">
      We recommend starting with a <strong>{plan}</strong> on DigitalOcean
      — {note}. Total infrastructure cost: <strong>{cost}/month</strong>
      regardless of team size, vs per-seat pricing forever.
    </p>
    <div style="display:flex;gap:0.75rem;flex-wrap:wrap;margin-bottom:0.75rem;">
      <a href="{do_link}" target="_blank" rel="noopener sponsored"
         style="display:inline-flex;align-items:center;gap:7px;
                background:#0080FF;color:#fff;padding:0.6rem 1.25rem;
                border-radius:8px;text-decoration:none;font-weight:700;
                font-size:0.88rem;transition:opacity 0.15s;"
         onmouseover="this.style.opacity='.9'" onmouseout="this.style.opacity='1'">
        <img src="https://cdn.simpleicons.org/digitalocean/ffffff" width="18" height="18" alt="DigitalOcean">
        DigitalOcean — $200 free credit
      </a>
      <a href="{vultr_link}" target="_blank" rel="noopener sponsored"
         style="display:inline-flex;align-items:center;gap:7px;
                background:#fff;color:#007BFC;border:2px solid #007BFC;
                padding:0.6rem 1.25rem;border-radius:8px;text-decoration:none;
                font-weight:700;font-size:0.88rem;">
        <img src="https://cdn.simpleicons.org/vultr/007BFC" width="18" height="18" alt="Vultr">
        Vultr — $100 free credit
      </a>
    </div>
    <p style="font-size:0.72rem;color:#A0AEC0;margin:0;">
      Affiliate disclosure: we earn a small commission if you sign up.
      It costs you nothing and helps us keep this site free.
    </p>
  </div>"""


# ── STEP 2: In build_site() inside the comparison page loop ──────────────────
# Find this section (around line 1200 in publish_github_pages.py):
#
#   migration_link_html = f"""..."""
#
# BEFORE that line, add:
#
#   vps_block_html = build_vps_block(oss_key, oss_name)
#
# Then in the COMPARISON_PAGE.format() call, add:
#   vps_block=vps_block_html,
#
# And in the COMPARISON_PAGE template string, add {vps_block} right after
# {migration_link}:
#   {migration_link}
#   {vps_block}       ← add this line


# ── STEP 3: Also add to migration pages ──────────────────────────────────────
# In build_migration_page(), find the savings_box div and add
# build_vps_block(oss_key, oss_name) right after it.
#
# The migration page is the highest-intent moment — someone who just decided
# to switch and is looking for how to do it is already primed to buy hosting.


# ── VERIFICATION: after adding, check these pages have the block: ─────────────
EXPECTED_PAGES = [
    "slack-vs-mattermost",
    "github-vs-gitea",
    "zoom-vs-jitsi",
    "notion-vs-appflowy",   # AppFlowy is local-first so skip VPS
    "figma-vs-penpot",
    "jira-vs-plane",
    "dropbox-vs-nextcloud",
]

if __name__ == "__main__":
    print("VPS Affiliate Block Preview")
    print("=" * 60)
    block = build_vps_block("mattermost", "Mattermost")
    # Strip HTML tags for readable preview
    import re
    text = re.sub(r'<[^>]+>', '', block)
    text = re.sub(r'\s+', ' ', text).strip()
    print(text[:500])
    print("\n" + "=" * 60)
    print("This block will appear on all self-hostable comparison pages.")
    print("\nTools with VPS blocks enabled:")
    for key, (plan, cost, note) in VPS_SETUP_COST.items():
        print(f"  {key}: {plan} ({cost}/mo)")
