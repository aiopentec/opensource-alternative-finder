#!/usr/bin/env python3
"""
generate_pinterest_pins.py
──────────────────────────
Batch-generates 1000×1500 Pinterest pins for every comparison pair
in .cache/publish/comparisons_*.json.

Two visual templates per comparison:
  • Template A — Dark tech  (dark navy + blue header)
  • Template B — Bold light (dark hook + white body)

Output: pinterest_pins/template_a/<slug>.png
        pinterest_pins/template_b/<slug>.png

Usage:
  python scripts/generate_pinterest_pins.py              # all 63 pairs × 2 templates
  python scripts/generate_pinterest_pins.py --limit 5   # first 5 pairs only
  python scripts/generate_pinterest_pins.py --slug figma-vs-penpot
  python scripts/generate_pinterest_pins.py --template a  # dark only
  python scripts/generate_pinterest_pins.py --template b  # light only
  python scripts/generate_pinterest_pins.py --team-size 50

Requires: pip install playwright && playwright install chromium
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
CACHE_DIR  = ".data/cache"
OUTPUT_DIR = "pinterest_pins"
PIN_W, PIN_H = 1000, 1500
SITE_URL   = "https://osalfinder.com"

# ── Simple Icons CDN slug map (tool name → slug) ──────────────────────────────
# CDN: https://cdn.jsdelivr.net/npm/simple-icons/icons/<slug>.svg
SIMPLEICONS_SLUGS = {
    # Proprietary
    "Slack":              "slack",
    "Microsoft Teams":    "microsoftteams",
    "Discord":            "discord",
    "Notion":             "notion",
    "Google Workspace":   "google",
    "Airtable":           "airtable",
    "Mailchimp":          "mailchimp",
    "Figma":              "figma",
    "Jira":               "jira",
    "Trello":             "trello",
    "Dropbox":            "dropbox",
    "Zoom":               "zoom",
    "Linear":             "linear",
    "Asana":              "asana",
    "Monday.com":         "monday",
    "HubSpot":            "hubspot",
    "Confluence":         "confluence",
    "Zendesk":            "zendesk",
    "Calendly":           "calendly",
    "Intercom":           "intercom",
    "Postman":            "postman",
    "1Password":          "1password",
    "Adobe Photoshop":    "adobephotoshop",
    "Adobe Illustrator":  "adobeillustrator",
    "Adobe Premiere":     "adobepremierepro",
    "Adobe XD":           "adobe",
    "Adobe Audition":     "adobeaudition",
    "Typeform":           "typeform",
    "Miro":               "miro",
    "Netlify":            "netlify",
    "Salesforce":         "salesforce",
    "Grammarly":          "grammarly",
    "Shopify":            "shopify",
    "LastPass":           "lastpass",
    "QuickBooks":         "quickbooks",
    "DocuSign":           "docusign",
    "Sentry":             "sentry",
    "Hotjar":             "hotjar",
    "Loom":               "loom",
    "Canva":              "canva",
    "Sketch":             "sketch",
    "Framer":             "framer",
    "StreamYard":         "youtube",   # no official icon, use generic
    "Wix":                "wix",
    "Squarespace":        "squarespace",
    "Webflow":            "webflow",
    "OpenAI API":         "openai",
    "Zoho CRM":           "zoho",
    # Open source
    "Mattermost":         "mattermost",
    "Element":            "element",
    "Zulip":              "zulip",
    "AppFlowy":           "appflowy",
    "Obsidian":           "obsidian",
    "Logseq":             "logseq",
    "GitLab":             "gitlab",
    "Gitea":              "gitea",
    "Penpot":             "penpot",
    "Inkscape":           "inkscape",
    "Plane":              "plane",
    "WeKan":              "wekan",
    "Nextcloud":          "nextcloud",
    "Jitsi Meet":         "jitsi",
    "Taiga":              "taiga",
    "NocoDB":             "nocodb",
    "SuiteCRM":           "suitecrm",
    "Listmonk":           "listmonk",
    "Ghost":              "ghost",
    "Bitwarden":          "bitwarden",
    "Vaultwarden":        "bitwarden",
    "LanguageTool":       "languagetool",
    "Cal.com":            "caldotcom",
    "Chatwoot":           "chatwoot",
    "Hoppscotch":         "hoppscotch",
    "BookStack":          "bookstack",
    "Excalidraw":         "excalidraw",
    "Coolify":            "coolify",
    "OBS Studio":         "obsstudio",
    "Audacity":           "audacity",
    "Kdenlive":           "kdenlive",
    "GIMP":               "gimp",
    "WordPress.org":      "wordpress",
    "WooCommerce":        "woocommerce",
    "Akaunting":          "akaunting",
    "Ollama":             "ollama",
}

# ── Category display names and accent colours ─────────────────────────────────
CATEGORY_META = {
    "communication":      {"label": "Communication",       "color": "#2ECC71"},
    "productivity":       {"label": "Productivity",        "color": "#3498DB"},
    "developer-tools":    {"label": "Developer Tools",     "color": "#9B59B6"},
    "design":             {"label": "Design",              "color": "#E91E63"},
    "project-management": {"label": "Project Management",  "color": "#F39C12"},
    "file-storage":       {"label": "File Storage",        "color": "#1ABC9C"},
    "video-conferencing": {"label": "Video Conferencing",  "color": "#E74C3C"},
    "general":            {"label": "Tools",               "color": "#95A5A6"},
}

# ── Self-hosting difficulty lookup (oss_key → info) ───────────────────────────
HOSTING_DIFFICULTY = {
    "element":     {"label": "Moderate",   "time": "~2 hours"},
    "mattermost":  {"label": "Easy",       "time": "~30 mins"},
    "zulip":       {"label": "Moderate",   "time": "~1–2 hours"},
    "appflowy":    {"label": "Very Easy",  "time": "~5 mins"},
    "obsidian":    {"label": "Very Easy",  "time": "~2 mins"},
    "logseq":      {"label": "Very Easy",  "time": "~2 mins"},
    "gitlab":      {"label": "Advanced",   "time": "~3–4 hours"},
    "gitea":       {"label": "Easy",       "time": "~20 mins"},
    "penpot":      {"label": "Easy",       "time": "~30 mins"},
    "inkscape":    {"label": "Very Easy",  "time": "~5 mins"},
    "plane":       {"label": "Easy",       "time": "~30 mins"},
    "wekan":       {"label": "Easy",       "time": "~20 mins"},
    "nextcloud":   {"label": "Moderate",   "time": "~1–2 hours"},
    "jitsi":       {"label": "Easy",       "time": "~30 mins"},
    "taiga":       {"label": "Moderate",   "time": "~1–2 hours"},
    "nocodb":      {"label": "Very Easy",  "time": "~5 mins"},
    "suitecrm":    {"label": "Moderate",   "time": "~1–2 hours"},
    "espocrm":     {"label": "Easy",       "time": "~20 mins"},
    "listmonk":    {"label": "Easy",       "time": "~20 mins"},
    "ghost":       {"label": "Easy",       "time": "~20 mins"},
    "bitwarden":   {"label": "Easy",       "time": "~20 mins"},
    "vaultwarden": {"label": "Easy",       "time": "~15 mins"},
    "docuseal":    {"label": "Easy",       "time": "~15 mins"},
    "glitchtip":   {"label": "Easy",       "time": "~20 mins"},
    "openreplay":  {"label": "Moderate",   "time": "~1 hour"},
    "coolify":     {"label": "Easy",       "time": "~15 mins"},
    "wordpress-org":{"label":"Easy",       "time": "~10 mins"},
    "woocommerce": {"label": "Easy",       "time": "~15 mins"},
    "akaunting":   {"label": "Easy",       "time": "~20 mins"},
    "dolibarr":    {"label": "Moderate",   "time": "~1 hour"},
    "vtiger":      {"label": "Moderate",   "time": "~1 hour"},
    "ollama":      {"label": "Very Easy",  "time": "~5 mins"},
}

# ── Per-tool bullet features (4 points each, for the oss_key) ─────────────────
TOOL_FEATURES = {
    "mattermost":   ["Open-source Slack replacement", "Self-hosted — own every message", "Threads, channels, and file sharing", "Docker setup in 30 minutes"],
    "element":      ["End-to-end encrypted by default", "Decentralised Matrix protocol", "Bridges to Slack, Teams, WhatsApp", "Self-host on any Linux server"],
    "zulip":        ["Threaded topics reduce noise", "Powerful full-text search", "Organised streams and topics", "Excellent keyboard shortcuts"],
    "appflowy":     ["Local-first — works fully offline", "Kanban, docs, and grid databases", "No per-user cost ever", "Export to Markdown anytime"],
    "obsidian":     ["Local files — no cloud required", "Powerful bi-directional linking", "600+ community plugins", "Works offline, always yours"],
    "logseq":       ["Outliner + daily journal hybrid", "Plain-text Markdown files", "Local-first, no cloud lock-in", "Graph view of linked notes"],
    "gitlab":       ["Complete CI/CD pipeline built-in", "Container registry included", "Issue tracking + merge requests", "Self-host with Docker or Omnibus"],
    "gitea":        ["Lightweight — runs on a Raspberry Pi", "GitHub-like interface", "Docker setup in 20 minutes", "Full Git hosting with web UI"],
    "penpot":       ["Browser-based, real-time collaboration", "SVG-native open file format", "Works like Figma — costs nothing", "Docker Compose setup in 30 mins"],
    "inkscape":     ["Professional SVG vector editor", "Import and export AI, EPS, PDF", "Full desktop application", "No subscription, ever"],
    "gimp":         ["Professional image manipulation", "Layer-based non-destructive editing", "Supports PSD and AI files", "Script-Fu automation support"],
    "kdenlive":     ["Multi-track video editor", "Proxy clip for smooth editing", "Export to any format", "Active development community"],
    "audacity":     ["Multi-track audio editing", "Real-time effects and VST plugins", "Export to MP3, WAV, FLAC", "Noise reduction and EQ built-in"],
    "obs":          ["Industry-standard live streaming", "Scene transitions and overlays", "Multi-platform support", "Large plugin ecosystem"],
    "plane":        ["GitHub-style issue tracking", "Kanban, list, and board views", "Project roadmaps and sprints", "REST API + integrations"],
    "wekan":        ["Identical to Trello's interface", "Custom fields and swimlanes", "Webhooks and integrations", "Docker setup in 20 minutes"],
    "nextcloud":    ["Files, calendar, contacts, and mail", "End-to-end encryption option", "Desktop and mobile sync apps", "Full Google Workspace replacement"],
    "jitsi":        ["No account needed to join calls", "Works in any browser instantly", "Self-host for full call privacy", "Unlimited participants and meetings"],
    "taiga":        ["Agile sprints and backlogs", "Scrum and Kanban boards", "Time tracking built-in", "REST API for integrations"],
    "nocodb":       ["Spreadsheet interface over any DB", "REST API auto-generated", "Connect to existing databases", "Forms, galleries, and calendar views"],
    "suitecrm":     ["Full CRM — leads, deals, contacts", "Marketing automation included", "Reports and dashboards", "1,000+ integrations via plugins"],
    "espocrm":      ["Clean modern CRM interface", "Email marketing built-in", "Custom fields and modules", "Docker setup available"],
    "listmonk":     ["Send to millions with one server", "Analytics and open-rate tracking", "Import from Mailchimp easily", "Blazing fast — Go-powered"],
    "ghost":        ["Built-in newsletter and memberships", "Modern markdown editor", "SEO-optimised by default", "Full content ownership"],
    "bitwarden":    ["End-to-end encrypted vault", "Browser extensions and mobile apps", "Secure team password sharing", "Self-host with Docker in 15 mins"],
    "vaultwarden":  ["Bitwarden-compatible open-source fork", "Uses 1/10th the memory", "All browser extensions work natively", "Single binary — easy to run"],
    "languagetool": ["Grammar, style, and spell-check", "25+ language support", "Browser extension and API", "Self-host for full data privacy"],
    "glitchtip":    ["Sentry-compatible error tracking", "Team alerts and dashboards", "Performance monitoring included", "Docker Compose setup"],
    "openreplay":   ["Full session replay and heatmaps", "Network inspector built-in", "Privacy-friendly by design", "Self-host on your infrastructure"],
    "docuseal":     ["PDF form signing and sending", "Audit trail and certificate included", "REST API for automation", "Docker setup in 15 minutes"],
    "chatwoot":     ["Omnichannel inbox — email, chat, social", "Team collaboration on tickets", "CSAT surveys built-in", "Docker setup in minutes"],
    "zammad":       ["Multi-channel support tickets", "SLA tracking and reporting", "Knowledge base included", "Active open-source community"],
    "bookstack":    ["Wiki-style docs with chapters", "Full-text search across all pages", "LDAP and SAML authentication", "Docker setup in 20 minutes"],
    "hoppscotch":   ["REST, GraphQL, WebSocket testing", "Real-time team collaboration", "Works in any browser instantly", "No account needed to start"],
    "formbricks":   ["Drag-and-drop form builder", "Logic branching and conditions", "GDPR-compliant by default", "One-line embed anywhere"],
    "excalidraw":   ["Real-time collaborative whiteboard", "Hand-drawn visual style", "Export to SVG or PNG", "Works offline in any browser"],
    "coolify":      ["Heroku-like UI on your own server", "Docker Compose and Swarm support", "Automatic SSL certificates", "Deploy from GitHub in seconds"],
    "cal-com":      ["Fully customisable booking page", "Zapier and webhook integrations", "Unlimited event types", "White-label ready"],
    "plasmic":      ["Visual page builder for React/Next", "Export clean production code", "CMS integration ready", "Design to code in minutes"],
    "cap":          ["Screen recording with annotation", "Instant shareable link", "Self-host for privacy", "Mac, Windows, and Linux"],
    "woocommerce":  ["Sell anything from WordPress", "80,000+ extensions available", "Full checkout customisation", "No monthly licensing fee"],
    "wordpress-org":["60,000+ plugins ecosystem", "Full ownership of your content", "WooCommerce for e-commerce", "One-click hosting setups"],
    "akaunting":    ["Invoicing and expense tracking", "Multi-currency support", "Client and vendor portals", "Docker setup available"],
    "dolibarr":     ["ERP + CRM in one package", "Invoicing, HR, and inventory", "500+ modules available", "LAMP or Docker deployment"],
    "vtiger":       ["Sales pipeline management", "Marketing automation included", "Customer support module", "Active development community"],
    "ollama":       ["Run LLMs locally — Mac, Windows, Linux", "No API costs or rate limits", "OpenAI-compatible local API", "Llama, Mistral, Gemma support"],
}

# Category fallback (used if oss_key not in TOOL_FEATURES)
CATEGORY_FEATURES = {
    "communication":      ["Team messaging and channels", "File sharing and search", "Self-hosted — own your data", "Easy Docker setup"],
    "productivity":       ["Full parity with the paid tool", "Local-first — works offline", "No per-user pricing ever", "Export your data anytime"],
    "developer-tools":    ["Git hosting with web UI", "Issue tracking and CI/CD", "Self-host on any server", "Active open-source community"],
    "design":             ["Professional-grade design tools", "Open file formats — no lock-in", "Real-time collaboration", "Self-host or use cloud version"],
    "project-management": ["Kanban, list, and board views", "Team assignments and deadlines", "No per-seat pricing", "Docker setup in minutes"],
    "file-storage":       ["Sync, share, and collaborate", "Encryption option available", "Desktop and mobile apps", "Run on your own server"],
    "video-conferencing": ["HD video and screen sharing", "No account needed to join", "Works in any browser", "Unlimited meetings and users"],
    "general":            ["Open-source — inspect the code", "Self-host — own all your data", "Active community and updates", "No vendor lock-in"],
}

DEFAULT_FEATURES = ["Open-source alternative", "Self-hosted — own your data", "No per-user licensing cost", "Active community and updates"]


# ── Utilities ─────────────────────────────────────────────────────────────────

def extract_monthly_price(pricing_str: str) -> float:
    """Pull first numeric value from a pricing string like '$8.75/user/month'."""
    if not pricing_str:
        return 0.0
    nums = re.findall(r"\d+(?:\.\d+)?", pricing_str.split("–")[0].split("/")[0])
    return float(nums[0]) if nums else 0.0


def format_savings(monthly_per_user: float, team_size: int) -> str:
    annual = int(monthly_per_user * team_size * 12)
    if annual == 0:
        return None
    if annual >= 10000:
        return f"${annual:,}"
    return f"${annual:,}"


def logo_img(tool_name: str, size: int, dark: bool = False) -> str:
    """
    Returns an <img> tag pointing to Simple Icons CDN with a JS fallback
    letter-avatar that fires via onerror if the slug 404s.
    dark=True applies a white filter (for dark backgrounds).
    """
    slug = SIMPLEICONS_SLUGS.get(tool_name, "")
    initial = (tool_name[0] if tool_name else "?").upper()
    filter_s = "filter:brightness(0) invert(1);opacity:0.9;" if dark else "opacity:0.85;"
    sz = size
    fsz = sz // 2

    fallback_div = (
        f'<div data-fb style="'
        f'display:none;width:{sz}px;height:{sz}px;border-radius:10px;'
        f'background:#374151;align-items:center;justify-content:center;'
        f'font-size:{fsz}px;font-weight:900;color:#fff;flex-shrink:0;">'
        f'{initial}</div>'
    )
    if not slug:
        # No CDN slug known — return letter avatar directly
        return (
            f'<div style="width:{sz}px;height:{sz}px;border-radius:10px;'
            f'background:#374151;display:flex;align-items:center;'
            f'justify-content:center;font-size:{fsz}px;font-weight:900;'
            f'color:#fff;flex-shrink:0;">{initial}</div>'
        )

    cdn = f"https://cdn.jsdelivr.net/npm/simple-icons/icons/{slug}.svg"
    return (
        f'<span style="position:relative;display:inline-flex;flex-shrink:0;'
        f'width:{sz}px;height:{sz}px;">'
        f'<img src="{cdn}" class="si-logo" '
        f'style="width:{sz}px;height:{sz}px;border-radius:8px;{filter_s}" '
        f'alt="{tool_name}" '
        f'onerror="this.style.display=\'none\';'
        f'this.nextElementSibling.style.display=\'flex\';">'
        f'{fallback_div}'
        f'</span>'
    )


def get_features(oss_key: str, category: str) -> list:
    return (
        TOOL_FEATURES.get(oss_key)
        or CATEGORY_FEATURES.get(category)
        or DEFAULT_FEATURES
    )


def get_difficulty(oss_key: str) -> dict:
    return HOSTING_DIFFICULTY.get(oss_key, {"label": "Moderate", "time": "~1 hour"})


# ── HTML generators ───────────────────────────────────────────────────────────

LOGO_FALLBACK_SCRIPT = """
<script>
document.querySelectorAll('.si-logo').forEach(function(img){
  if(img.complete && img.naturalWidth === 0){
    img.style.display='none';
    img.nextElementSibling.style.display='flex';
  }
});
</script>
"""

def gen_template_a(comp: dict, team_size: int) -> str:
    """Dark tech template — navy background, blue header, green savings block."""
    prop_name  = comp.get("proprietary_tool", "")
    oss_name   = comp.get("oss_tool", "")
    category   = comp.get("category", "general")
    cat_meta   = CATEGORY_META.get(category, CATEGORY_META["general"])
    pricing    = comp.get("proprietary_pricing", "")
    slug       = comp.get("slug", "")

    monthly    = extract_monthly_price(pricing)
    savings    = format_savings(monthly, team_size)
    features   = get_features(comp.get("oss_key", ""), category)
    diff       = get_difficulty(comp.get("oss_key", ""))

    prop_logo  = logo_img(prop_name, size=52, dark=True)
    oss_logo   = logo_img(oss_name,  size=52, dark=True)

    prop_price_display = pricing if pricing else "Paid"
    oss_price_display  = comp.get("oss_pricing", "Free (self-hosted)")

    savings_block = ""
    if savings:
        savings_block = f"""
    <div style="background:#1A7A3F;border-radius:18px;padding:28px 32px;
                display:flex;align-items:center;justify-content:space-between;">
      <div>
        <div style="font-size:22px;text-transform:uppercase;letter-spacing:.1em;
                    color:rgba(255,255,255,.6);margin-bottom:8px;">Annual savings</div>
        <div style="font-size:72px;font-weight:900;color:#fff;line-height:1;">{savings}</div>
        <div style="font-size:24px;color:rgba(255,255,255,.55);margin-top:8px;">
          for a {team_size}-person team
        </div>
      </div>
      <div style="font-size:80px;">&#128184;</div>
    </div>"""
    else:
        savings_block = f"""
    <div style="background:#1A7A3F;border-radius:18px;padding:28px 32px;">
      <div style="font-size:28px;font-weight:800;color:#fff;">Free to self-host</div>
      <div style="font-size:22px;color:rgba(255,255,255,.65);margin-top:8px;">
        Pay only server costs (~$5–20/month)
      </div>
    </div>"""

    features_html = ""
    for feat in features[:4]:
        features_html += f"""
    <div style="display:flex;align-items:flex-start;gap:18px;margin-bottom:18px;">
      <div style="width:38px;height:38px;border-radius:50%;background:#1A7A3F;
                  display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:2px;">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <polyline points="3,10 8,15 17,4" stroke="#fff" stroke-width="3"
                    stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div style="font-size:28px;color:rgba(255,255,255,.85);line-height:1.4;">{feat}</div>
    </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ width:{PIN_W}px; height:{PIN_H}px; font-family:'Segoe UI',-apple-system,sans-serif;
          background:#0F1923; display:flex; flex-direction:column; }}
</style>
</head>
<body>
  <!-- Accent bar -->
  <div style="height:12px;background:#1A7A3F;flex-shrink:0;"></div>

  <!-- Blue header -->
  <div style="background:#1F5C99;padding:40px 48px 32px;flex-shrink:0;">
    <div style="font-size:20px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;
                color:rgba(255,255,255,.5);margin-bottom:24px;">
      {cat_meta['label']} · free alternative
    </div>
    <!-- Tool logos + names -->
    <div style="display:flex;align-items:center;gap:22px;margin-bottom:28px;">
      <div style="display:flex;align-items:center;gap:14px;">
        {prop_logo}
        <span style="font-size:42px;font-weight:900;color:#FF6B6B;
                     text-decoration:line-through;text-decoration-color:rgba(255,107,107,.4);">
          {prop_name}
        </span>
      </div>
      <span style="background:rgba(255,255,255,.12);color:rgba(255,255,255,.55);
                   font-size:22px;font-weight:800;padding:8px 16px;border-radius:8px;
                   letter-spacing:.1em;">VS</span>
      <div style="display:flex;align-items:center;gap:14px;">
        {oss_logo}
        <span style="font-size:42px;font-weight:900;color:#ffffff;">{oss_name}</span>
      </div>
    </div>
    {savings_block}
  </div>

  <!-- Body -->
  <div style="padding:36px 48px;flex:1;display:flex;flex-direction:column;">
    <div style="font-size:22px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;
                color:rgba(255,255,255,.3);margin-bottom:20px;">Why teams are switching</div>
    {features_html}
    <div style="height:2px;background:rgba(255,255,255,.06);margin:20px 0;"></div>

    <!-- Head-to-head pricing -->
    <div style="font-size:22px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;
                color:rgba(255,255,255,.3);margin-bottom:16px;">Head to head</div>
    <div style="display:flex;gap:16px;margin-bottom:20px;">
      <div style="flex:1;background:rgba(255,255,255,.04);border:2px solid rgba(255,255,255,.07);
                  border-radius:14px;padding:20px 22px;">
        <div style="font-size:20px;color:rgba(255,255,255,.3);text-transform:uppercase;
                    letter-spacing:.1em;margin-bottom:8px;">{prop_name}</div>
        <div style="font-size:30px;font-weight:700;color:#FF6B6B;">{prop_price_display}</div>
      </div>
      <div style="flex:1;background:rgba(255,255,255,.04);border:2px solid rgba(255,255,255,.07);
                  border-radius:14px;padding:20px 22px;">
        <div style="font-size:20px;color:rgba(255,255,255,.3);text-transform:uppercase;
                    letter-spacing:.1em;margin-bottom:8px;">{oss_name}</div>
        <div style="font-size:30px;font-weight:700;color:#3DD68C;">{oss_price_display.split('(')[0].strip()}</div>
      </div>
      <div style="flex:1;background:rgba(255,255,255,.04);border:2px solid rgba(255,255,255,.07);
                  border-radius:14px;padding:20px 22px;">
        <div style="font-size:20px;color:rgba(255,255,255,.3);text-transform:uppercase;
                    letter-spacing:.1em;margin-bottom:8px;">Setup</div>
        <div style="font-size:30px;font-weight:700;color:#4A9FE0;">{diff['time']}</div>
      </div>
    </div>

    <!-- Migration note -->
    <div style="height:2px;background:rgba(255,255,255,.06);margin-bottom:20px;"></div>
    <div style="font-size:22px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;
                color:rgba(255,255,255,.3);margin-bottom:14px;">Migration</div>
    <div style="background:rgba(26,122,63,.15);border-left:8px solid #1A7A3F;
                border-radius:0 14px 14px 0;padding:22px 28px;">
      <div style="font-size:20px;color:rgba(255,255,255,.35);text-transform:uppercase;
                  letter-spacing:.1em;margin-bottom:8px;">Difficulty: {diff['label']}</div>
      <div style="font-size:24px;color:rgba(255,255,255,.72);line-height:1.5;">
        Most teams complete in one weekend. Full step-by-step guide at {SITE_URL}/{slug}/
      </div>
    </div>
  </div>

  <!-- Footer -->
  <div style="background:#141E28;padding:28px 48px;display:flex;align-items:center;
              justify-content:space-between;border-top:2px solid rgba(255,255,255,.06);
              flex-shrink:0;margin-top:auto;">
    <div style="font-size:30px;font-weight:700;color:rgba(255,255,255,.4);">
      <span style="color:#4A9FE0;">OSAL</span>finder.com
    </div>
    <div style="background:#1F5C99;color:#fff;font-size:24px;font-weight:700;
                padding:16px 28px;border-radius:12px;">Full comparison &rarr;</div>
  </div>
  {LOGO_FALLBACK_SCRIPT}
</body>
</html>"""


def gen_template_b(comp: dict, team_size: int) -> str:
    """Bold light template — dark hook, side-by-side tool bar, white body."""
    prop_name  = comp.get("proprietary_tool", "")
    oss_name   = comp.get("oss_tool", "")
    category   = comp.get("category", "general")
    cat_meta   = CATEGORY_META.get(category, CATEGORY_META["general"])
    pricing    = comp.get("proprietary_pricing", "")
    slug       = comp.get("slug", "")

    monthly    = extract_monthly_price(pricing)
    savings    = format_savings(monthly, team_size)
    features   = get_features(comp.get("oss_key", ""), category)
    diff       = get_difficulty(comp.get("oss_key", ""))

    prop_logo_b = logo_img(prop_name, size=64, dark=False)
    oss_logo_b  = logo_img(oss_name,  size=64, dark=False)

    prop_price_display = pricing if pricing else "Paid plan"
    oss_price_display  = comp.get("oss_pricing", "Free (self-hosted)")

    savings_hero = ""
    if savings:
        savings_hero = f"""
      <div style="font-size:76px;font-weight:900;color:#1A7A3F;line-height:1;">{savings}/yr</div>
      <div style="font-size:24px;color:#718096;margin-top:10px;">
        saved by a {team_size}-person team switching to {oss_name}
      </div>"""
    else:
        savings_hero = f"""
      <div style="font-size:44px;font-weight:900;color:#1A7A3F;line-height:1.1;">
        $0/month in licensing fees
      </div>
      <div style="font-size:22px;color:#718096;margin-top:10px;">
        Pay only server costs (~$5–20/month total)
      </div>"""

    pills_html = ""
    for feat in features[:5]:
        pills_html += f"""
      <div style="background:#F0F4F8;border:2px solid #E2E8F0;border-radius:40px;
                  padding:10px 20px;font-size:22px;font-weight:600;color:#2D3748;
                  display:flex;align-items:center;gap:10px;">
        <div style="width:10px;height:10px;border-radius:50%;background:#1A7A3F;flex-shrink:0;"></div>
        {feat}
      </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ width:{PIN_W}px; height:{PIN_H}px; font-family:'Segoe UI',-apple-system,sans-serif;
          background:#ffffff; display:flex; flex-direction:column; }}
</style>
</head>
<body>
  <!-- Dark hook -->
  <div style="background:#1A202C;padding:44px 48px 38px;flex-shrink:0;">
    <div style="font-size:22px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;
                color:rgba(255,255,255,.4);margin-bottom:18px;">
      {cat_meta['label']} · open source
    </div>
    <div style="font-size:52px;font-weight:900;color:#ffffff;line-height:1.15;margin-bottom:26px;">
      Stop paying for <span style="color:#FF6B6B;">{prop_name}.</span>
    </div>
    <div style="display:inline-flex;align-items:center;background:#1A7A3F;color:#fff;
                font-size:24px;font-weight:700;padding:12px 28px;border-radius:40px;">
      Free alternative exists
    </div>
  </div>

  <!-- Side-by-side tool comparison bar -->
  <div style="display:flex;align-items:stretch;flex-shrink:0;">
    <div style="flex:1;padding:28px 22px;display:flex;flex-direction:column;align-items:center;
                gap:10px;background:#FDF2F2;border-bottom:6px solid #E53E3E;">
      {prop_logo_b}
      <span style="font-size:30px;font-weight:900;color:#C0392B;">{prop_name}</span>
      <span style="font-size:22px;font-weight:700;color:#C0392B;">{prop_price_display}</span>
      <span style="font-size:18px;font-weight:700;padding:5px 16px;border-radius:30px;
                   background:#FDE8E8;color:#C0392B;">PAID</span>
    </div>
    <div style="width:4px;background:#F0F4F8;flex-shrink:0;"></div>
    <div style="flex:1;padding:28px 22px;display:flex;flex-direction:column;align-items:center;
                gap:10px;background:#EAFAF1;border-bottom:6px solid #1A7A3F;">
      {oss_logo_b}
      <span style="font-size:30px;font-weight:900;color:#1A7A3F;">{oss_name}</span>
      <span style="font-size:22px;font-weight:700;color:#1A7A3F;">$0/user/month</span>
      <span style="font-size:18px;font-weight:700;padding:5px 16px;border-radius:30px;
                   background:#D5F5E3;color:#1A7A3F;">FREE</span>
    </div>
  </div>

  <!-- Body -->
  <div style="padding:36px 48px;flex:1;display:flex;flex-direction:column;">
    <!-- Savings hero -->
    <div style="text-align:center;margin-bottom:28px;padding-bottom:26px;
                border-bottom:2px solid #F0F4F8;">
      {savings_hero}
    </div>

    <!-- Feature pills -->
    <div style="font-size:20px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;
                color:#A0AEC0;margin-bottom:16px;">What you get for free</div>
    <div style="display:flex;flex-wrap:wrap;gap:12px;margin-bottom:28px;">
      {pills_html}
    </div>

    <!-- Setup stats -->
    <div style="font-size:20px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;
                color:#A0AEC0;margin-bottom:16px;">Setup details</div>
    <div style="display:flex;gap:14px;margin-bottom:28px;">
      <div style="flex:1;background:#EBF4FA;border-radius:14px;padding:20px;text-align:center;">
        <div style="font-size:18px;color:#4A90C4;text-transform:uppercase;letter-spacing:.08em;
                    margin-bottom:6px;">Difficulty</div>
        <div style="font-size:28px;font-weight:700;color:#1F5C99;">{diff['label']}</div>
      </div>
      <div style="flex:1;background:#EBF4FA;border-radius:14px;padding:20px;text-align:center;">
        <div style="font-size:18px;color:#4A90C4;text-transform:uppercase;letter-spacing:.08em;
                    margin-bottom:6px;">Setup time</div>
        <div style="font-size:28px;font-weight:700;color:#1F5C99;">{diff['time']}</div>
      </div>
      <div style="flex:1;background:#EBF4FA;border-radius:14px;padding:20px;text-align:center;">
        <div style="font-size:18px;color:#4A90C4;text-transform:uppercase;letter-spacing:.08em;
                    margin-bottom:6px;">Data export</div>
        <div style="font-size:28px;font-weight:700;color:#1F5C99;">Full</div>
      </div>
    </div>

    <!-- Migration note -->
    <div style="font-size:20px;font-weight:700;text-transform:uppercase;letter-spacing:.12em;
                color:#A0AEC0;margin-bottom:14px;">Migration</div>
    <div style="font-size:24px;color:#718096;line-height:1.6;background:#F8FAFC;
                border-radius:14px;padding:22px 28px;border-left:8px solid #1F5C99;">
      Step-by-step guide included. Most teams complete migration in one weekend.
      Full tutorial at {SITE_URL}/{slug}/
    </div>
  </div>

  <!-- Footer -->
  <div style="padding:26px 48px;background:#F0F4F8;display:flex;align-items:center;
              justify-content:space-between;border-top:2px solid #E2E8F0;
              flex-shrink:0;margin-top:auto;">
    <div style="font-size:30px;font-weight:700;color:#718096;">
      <span style="color:#1F5C99;font-weight:800;">OSAL</span>finder.com
    </div>
    <div style="background:#1F5C99;color:#fff;font-size:24px;font-weight:700;
                padding:16px 28px;border-radius:12px;">Compare now &rarr;</div>
  </div>
  {LOGO_FALLBACK_SCRIPT}
</body>
</html>"""


# ── Rendering ─────────────────────────────────────────────────────────────────

def render_all(comparisons: list, team_size: int, templates: str, output_dir: Path):
    from playwright.sync_api import sync_playwright

    dir_a = output_dir / "template_a"
    dir_b = output_dir / "template_b"
    if "a" in templates:
        dir_a.mkdir(parents=True, exist_ok=True)
    if "b" in templates:
        dir_b.mkdir(parents=True, exist_ok=True)

    total = len(comparisons) * len(templates)
    done  = 0
    t0    = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page    = browser.new_page(viewport={"width": PIN_W, "height": PIN_H})

        for i, comp in enumerate(comparisons, 1):
            slug = comp.get("slug", f"comparison-{i}")

            if "a" in templates:
                html = gen_template_a(comp, team_size)
                page.set_content(html, wait_until="networkidle")
                page.screenshot(path=str(dir_a / f"{slug}.png"))
                done += 1
                elapsed = time.time() - t0
                eta = (elapsed / done) * (total - done)
                print(f"  [A] {i}/{len(comparisons)} {slug} "
                      f"({elapsed:.0f}s elapsed, ~{eta:.0f}s remaining)")

            if "b" in templates:
                html = gen_template_b(comp, team_size)
                page.set_content(html, wait_until="networkidle")
                page.screenshot(path=str(dir_b / f"{slug}.png"))
                done += 1
                elapsed = time.time() - t0
                eta = (elapsed / done) * (total - done)
                print(f"  [B] {i}/{len(comparisons)} {slug} "
                      f"({elapsed:.0f}s elapsed, ~{eta:.0f}s remaining)")

        browser.close()

    print(f"\n✅ {done} PNGs written to {output_dir}/")


# ── Load comparisons ──────────────────────────────────────────────────────────

def load_comparisons(cache_dir: str) -> list:
    all_comps = []
    for f in sorted(Path(cache_dir).glob("comparisons_*.json")):
        with open(f) as fp:
            all_comps.extend(json.load(fp))

    # Deduplicate by slug
    seen, deduped = set(), []
    for c in all_comps:
        s = c.get("slug", "")
        if s and s not in seen:
            seen.add(s)
            deduped.append(c)
    return deduped


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Batch-generate Pinterest pins for all OSALFinder comparisons."
    )
    parser.add_argument(
        "--cache-dir", default=CACHE_DIR,
        help=f"Path to comparison JSON cache (default: {CACHE_DIR})"
    )
    parser.add_argument(
        "--output-dir", default=OUTPUT_DIR,
        help=f"Output directory for PNGs (default: {OUTPUT_DIR})"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only process the first N comparisons"
    )
    parser.add_argument(
        "--slug", default=None,
        help="Only process a single comparison by slug (e.g. figma-vs-penpot)"
    )
    parser.add_argument(
        "--template", choices=["a", "b", "ab"], default="ab",
        help="Which template(s) to render: a=dark tech, b=bold light, ab=both (default: ab)"
    )
    parser.add_argument(
        "--team-size", type=int, default=25,
        help="Team size used for savings calculation (default: 25)"
    )
    args = parser.parse_args()

    # Load
    comps = load_comparisons(args.cache_dir)
    if not comps:
        print(f"❌ No comparisons found in {args.cache_dir}")
        sys.exit(1)

    # Filter
    if args.slug:
        comps = [c for c in comps if c.get("slug") == args.slug]
        if not comps:
            print(f"❌ Slug '{args.slug}' not found")
            sys.exit(1)
    if args.limit:
        comps = comps[:args.limit]

    templates = args.template  # 'a', 'b', or 'ab'
    output_dir = Path(args.output_dir)

    print(f"📌 OSALFinder Pinterest Pin Generator")
    print(f"   Comparisons : {len(comps)}")
    print(f"   Templates   : {', '.join(f'Template {t.upper()}' for t in templates)}")
    print(f"   Team size   : {args.team_size} people")
    print(f"   Output      : {output_dir}/")
    print(f"   Total PNGs  : {len(comps) * len(templates)}")
    print()

    render_all(comps, args.team_size, templates, output_dir)

    print()
    print(f"   template_a/  →  dark tech pins")
    print(f"   template_b/  →  bold light pins")


if __name__ == "__main__":
    main()
