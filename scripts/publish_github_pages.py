#!/usr/bin/env python3
"""
publish_github_pages.py  —  OPTIMIZED VERSION
Converts generated JSON comparisons into a complete static website.

Improvements over v1:
  - Full SEO: meta tags, Open Graph, Twitter Cards, canonical URLs
  - Schema.org structured data (Article + BreadcrumbList)
  - Auto-generated sitemap.xml
  - Affiliate link injection for all major tools
  - Google AdSense placeholder (swap in your publisher ID)
  - Carbon Ads placeholder
  - Email capture widget
  - "Related comparisons" on every page
  - Performance: preconnect hints, lazy loading
  - 404 page
  - Better page titles for search ranking

Usage: python scripts/publish_github_pages.py
"""

import json, logging, os, re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)

# ── CONFIG — edit these ───────────────────────────────────────────────────────
SITE_BASE_URL  = os.getenv("SITE_BASE_URL", "https://aiopentec.github.io/opensource-alternative-finder")
ADSENSE_ID     = os.getenv("ADSENSE_ID", "")          # e.g. ca-pub-XXXXXXXXXXXXXXXX
CARBON_SERVE   = os.getenv("CARBON_SERVE", "")        # from carbonads.com
CARBON_PLACEMENT = os.getenv("CARBON_PLACEMENT", "")  # from carbonads.com
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_ICONS = {
    'communication':      '💬',
    'productivity':       '📝',
    'developer-tools':    '⚙️',
    'design':             '🎨',
    'project-management': '📋',
    'file-storage':       '☁️',
    'video-conferencing': '🎥',
    'general':            '🔧',
}

CATEGORY_COLORS = {
    'communication':      '#2ECC71',
    'productivity':       '#3498DB',
    'developer-tools':    '#9B59B6',
    'design':             '#E91E63',
    'project-management': '#F39C12',
    'file-storage':       '#1ABC9C',
    'video-conferencing': '#E74C3C',
    'general':            '#95A5A6',
}

# ── AFFILIATE LINKS ───────────────────────────────────────────────────────────
# Replace the # values with your actual affiliate URLs once you join each program
AFFILIATE_LINKS = {
    'slack':      'https://slack.com',           # slack.com/intl/affiliates
    'notion':     'https://notion.so',           # notion.so/affiliates — $10-16/signup
    'figma':      'https://figma.com',           # figma.com/affiliates — 20% first year
    'jira':       'https://atlassian.com/software/jira', # atlassian affiliate program
    'trello':     'https://trello.com',          # atlassian affiliate program
    'dropbox':    'https://dropbox.com',         # dropbox.com/affiliates — 10-25%
    'zoom':       'https://zoom.us',             # zoom.us/partners — 30% first year
    'linear':     'https://linear.app',          # linear.app/affiliates — 30% recurring
    'asana':      'https://asana.com',           # asana.com/partners
    'github':     'https://github.com',
    'discord':    'https://discord.com',
    # OSS tools — link to their official sites (no affiliate but builds trust)
    'element':    'https://element.io',
    'mattermost': 'https://mattermost.com',
    'zulip':      'https://zulip.com',
    'appflowy':   'https://appflowy.io',
    'obsidian':   'https://obsidian.md',
    'logseq':     'https://logseq.com',
    'gitlab':     'https://gitlab.com',
    'gitea':      'https://gitea.io',
    'penpot':     'https://penpot.app',
    'plane':      'https://plane.so',
    'wekan':      'https://wekan.github.io',
    'nextcloud':  'https://nextcloud.com',
    'jitsi':      'https://jitsi.org',
    'taiga':      'https://taiga.io',
}


def get_adsense_snippet():
    """Returns AdSense script tag if configured."""
    if not ADSENSE_ID:
        return '<!-- AdSense: set ADSENSE_ID env var to enable -->'
    return f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE_ID}" crossorigin="anonymous"></script>'


def get_adsense_unit():
    """Returns an in-content AdSense ad unit if configured."""
    if not ADSENSE_ID:
        return ''
    return f"""
  <div class="ad-unit" style="text-align:center; margin: 1.5rem 0;">
    <ins class="adsbygoogle"
         style="display:block"
         data-ad-client="{ADSENSE_ID}"
         data-ad-slot="auto"
         data-ad-format="auto"
         data-full-width-responsive="true"></ins>
    <script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
  </div>"""


def get_carbon_ad():
    """Returns Carbon Ads unit if configured."""
    if not CARBON_SERVE:
        return ''
    return f"""
  <div id="carbonads-container" style="margin: 1.5rem 0;">
    <script async type="text/javascript" src="//cdn.carbonads.com/carbon.js?serve={CARBON_SERVE}&placement={CARBON_PLACEMENT}" id="_carbonads_js"></script>
  </div>"""


def markdown_to_html(md: str) -> str:
    """Convert Markdown to HTML."""
    try:
        import markdown as md_lib
        return md_lib.markdown(md, extensions=['tables', 'nl2br'])
    except ImportError:
        pass

    html = md
    html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$',  r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$',   r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$',    r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', html)
    html = re.sub(r'\*\*(.+?)\*\*',     r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*',         r'<em>\1</em>', html)
    html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', html)
    html = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)

    lines = html.split('\n')
    result = []
    in_table = False
    header_done = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            if not in_table:
                result.append('<div class="table-wrapper"><table>')
                in_table = True
                header_done = False
            if re.match(r'^\|[\s\-|]+\|$', stripped):
                header_done = True
                continue
            cells = [c.strip() for c in stripped.strip('|').split('|')]
            if not header_done:
                result.append('<thead><tr>' + ''.join(f'<th>{c}</th>' for c in cells) + '</tr></thead><tbody>')
                header_done = True
            else:
                result.append('<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
        else:
            if in_table:
                result.append('</tbody></table></div>')
                in_table = False
                header_done = False
            result.append(line)
    if in_table:
        result.append('</tbody></table></div>')
    html = '\n'.join(result)

    def convert_list(text):
        lines = text.split('\n')
        out = []
        in_ul = False
        in_ol = False
        for line in lines:
            ul_match = re.match(r'^[-*] (.+)$', line)
            ol_match = re.match(r'^\d+\. (.+)$', line)
            if ul_match:
                if not in_ul:
                    if in_ol: out.append('</ol>'); in_ol = False
                    out.append('<ul>')
                    in_ul = True
                out.append(f'<li>{ul_match.group(1)}</li>')
            elif ol_match:
                if not in_ol:
                    if in_ul: out.append('</ul>'); in_ul = False
                    out.append('<ol>')
                    in_ol = True
                out.append(f'<li>{ol_match.group(1)}</li>')
            else:
                if in_ul: out.append('</ul>'); in_ul = False
                if in_ol: out.append('</ol>'); in_ol = False
                out.append(line)
        if in_ul: out.append('</ul>')
        if in_ol: out.append('</ol>')
        return '\n'.join(out)

    html = convert_list(html)
    html = html.replace('---', '<hr>')
    paras = re.split(r'\n{2,}', html)
    wrapped = []
    for p in paras:
        p = p.strip()
        if p and not re.match(r'^<(h[1-6]|ul|ol|table|div|blockquote|hr)', p):
            p = f'<p>{p}</p>'
        wrapped.append(p)
    return '\n'.join(wrapped)


# ── COMPARISON PAGE TEMPLATE ──────────────────────────────────────────────────
COMPARISON_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <!-- SEO -->
  <title>{seo_title}</title>
  <meta name="description" content="{seo_description}">
  <meta name="keywords" content="{prop_name} alternative, open source {prop_name}, free {prop_name} alternative, {oss_name} vs {prop_name}">
  <link rel="canonical" href="{canonical_url}">
  <meta name="robots" content="index, follow">

  <!-- Open Graph -->
  <meta property="og:type" content="article">
  <meta property="og:title" content="{seo_title}">
  <meta property="og:description" content="{seo_description}">
  <meta property="og:url" content="{canonical_url}">
  <meta property="og:site_name" content="Open Source Alternative Finder">

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{seo_title}">
  <meta name="twitter:description" content="{seo_description}">

  <!-- Schema.org structured data -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "{title}",
    "description": "{seo_description}",
    "dateModified": "{iso_date}",
    "publisher": {{
      "@type": "Organization",
      "name": "Open Source Alternative Finder",
      "url": "{site_base_url}"
    }},
    "breadcrumb": {{
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{"@type":"ListItem","position":1,"name":"Home","item":"{site_base_url}/"}},
        {{"@type":"ListItem","position":2,"name":"{category_label}","item":"{site_base_url}/{category_slug}/"}},
        {{"@type":"ListItem","position":3,"name":"{title}","item":"{canonical_url}"}}
      ]
    }}
  }}
  </script>

  <!-- Performance hints -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="dns-prefetch" href="https://pagead2.googlesyndication.com">

  {adsense_script}

  <link rel="icon" href="../favicon.ico" type="image/x-icon">
  <style>
    :root {{
      --blue: #1F5C99; --blue-light: #2980B9; --blue-bg: #EBF4FA;
      --green: #1A7A3F; --green-bg: #EAFAF1;
      --category: {category_color};
      --bg: #F0F4F8; --card: #FFFFFF;
      --text: #1A202C; --text-muted: #718096;
      --border: #E2E8F0; --shadow: 0 2px 8px rgba(0,0,0,0.08);
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.7; }}
    a {{ color: var(--blue); }}
    nav {{ background: var(--blue); padding: 0.75rem 1.5rem; display: flex; align-items: center; gap: 1rem; }}
    nav a {{ color: #fff; text-decoration: none; font-size: 0.9rem; opacity: 0.9; }}
    nav a:hover {{ opacity: 1; }}
    nav .sep {{ color: rgba(255,255,255,0.4); }}
    .hero {{ background: linear-gradient(135deg, var(--blue) 0%, var(--blue-light) 100%); color: #fff; padding: 3rem 1.5rem 2.5rem; text-align: center; }}
    .hero .category-badge {{ display: inline-block; background: var(--category); color: #fff; font-size: 0.75rem; font-weight: 700; padding: 0.3rem 0.9rem; border-radius: 20px; margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    .hero h1 {{ font-size: clamp(1.6rem, 4vw, 2.4rem); font-weight: 800; margin-bottom: 0.75rem; }}
    .hero .subtitle {{ opacity: 0.85; font-size: 1rem; max-width: 600px; margin: 0 auto 1.5rem; }}
    .hero-badges {{ display: flex; gap: 0.75rem; justify-content: center; flex-wrap: wrap; }}
    .hero-badge {{ background: rgba(255,255,255,0.18); border: 1px solid rgba(255,255,255,0.3); padding: 0.35rem 0.9rem; border-radius: 20px; font-size: 0.82rem; backdrop-filter: blur(4px); }}
    .quick-bar {{ background: #fff; border-bottom: 1px solid var(--border); padding: 1rem 1.5rem; }}
    .quick-bar-inner {{ max-width: 900px; margin: 0 auto; display: grid; grid-template-columns: 1fr auto 1fr; gap: 1rem; align-items: center; text-align: center; }}
    .qb-tool {{ padding: 0.75rem; border-radius: 8px; border: 2px solid var(--border); }}
    .qb-tool.proprietary {{ border-color: #E74C3C22; background: #FDF2F2; }}
    .qb-tool.opensource {{ border-color: #1A7A3F22; background: var(--green-bg); }}
    .qb-tool .label {{ font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); margin-bottom: 0.2rem; }}
    .qb-tool .name {{ font-size: 1.1rem; font-weight: 800; }}
    .qb-tool.proprietary .name {{ color: #C0392B; }}
    .qb-tool.opensource .name {{ color: var(--green); }}
    .qb-tool .price {{ font-size: 0.82rem; color: var(--text-muted); margin-top: 0.2rem; }}
    .qb-tool .visit-btn {{ display: inline-block; margin-top: 0.5rem; padding: 0.3rem 0.8rem; border-radius: 4px; font-size: 0.78rem; font-weight: 600; text-decoration: none; }}
    .qb-tool.proprietary .visit-btn {{ background: #FDE8E8; color: #C0392B; }}
    .qb-tool.opensource .visit-btn {{ background: #D5F5E3; color: var(--green); }}
    .vs-badge {{ font-size: 1.3rem; font-weight: 900; color: var(--blue); }}
    .content {{ max-width: 900px; margin: 2rem auto; padding: 0 1.5rem; }}
    .card {{ background: var(--card); border-radius: 12px; padding: 2rem; margin-bottom: 1.5rem; box-shadow: var(--shadow); border: 1px solid var(--border); }}
    .card h1 {{ display: none; }}
    .card h2 {{ font-size: 1.25rem; font-weight: 700; color: var(--blue); margin: 1.5rem 0 0.75rem; padding-bottom: 0.5rem; border-bottom: 2px solid var(--blue-bg); }}
    .card h2:first-child {{ margin-top: 0; }}
    .card h3 {{ font-size: 1.05rem; font-weight: 700; color: var(--text); margin: 1.25rem 0 0.5rem; }}
    .card p {{ margin: 0.5rem 0; color: var(--text); }}
    .card ul, .card ol {{ margin: 0.5rem 0 0.75rem 1.5rem; }}
    .card li {{ margin: 0.35rem 0; }}
    .card blockquote {{ background: var(--blue-bg); border-left: 4px solid var(--blue); padding: 0.75rem 1rem; border-radius: 0 6px 6px 0; margin: 0.75rem 0; font-size: 0.9rem; color: var(--text-muted); }}
    .card hr {{ border: none; border-top: 1px solid var(--border); margin: 1.5rem 0; }}
    .card em {{ color: var(--text-muted); font-size: 0.85rem; }}
    .card code {{ background: #F7FAFC; padding: 0.15rem 0.4rem; border-radius: 4px; font-family: 'Courier New', monospace; font-size: 0.85em; color: #E74C3C; }}
    .table-wrapper {{ overflow-x: auto; margin: 1rem 0; border-radius: 8px; border: 1px solid var(--border); }}
    table {{ width: 100%; border-collapse: collapse; }}
    thead th {{ background: var(--blue); color: #fff; padding: 0.7rem 1rem; text-align: left; font-size: 0.88rem; font-weight: 600; }}
    tbody td {{ padding: 0.65rem 1rem; border-bottom: 1px solid var(--border); font-size: 0.9rem; }}
    tbody tr:last-child td {{ border-bottom: none; }}
    tbody tr:nth-child(even) td {{ background: #F8FAFC; }}
    /* Related comparisons */
    .related-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.75rem; margin-top: 0.75rem; }}
    .related-link {{ display: block; padding: 0.65rem 0.9rem; background: #F8FAFC; border: 1px solid var(--border); border-radius: 8px; text-decoration: none; font-size: 0.85rem; font-weight: 600; color: var(--blue); transition: all 0.15s; }}
    .related-link:hover {{ background: var(--blue); color: #fff; border-color: var(--blue); }}
    /* Email capture */
    .email-box {{ background: linear-gradient(135deg, #1F5C99, #2980B9); color: #fff; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; text-align: center; }}
    .email-box h3 {{ font-size: 1.1rem; font-weight: 800; margin-bottom: 0.4rem; }}
    .email-box p {{ opacity: 0.85; font-size: 0.88rem; margin-bottom: 1rem; }}
    .email-form {{ display: flex; gap: 0.5rem; max-width: 400px; margin: 0 auto; flex-wrap: wrap; }}
    .email-form input {{ flex: 1; padding: 0.6rem 0.9rem; border: none; border-radius: 6px; font-size: 0.9rem; min-width: 180px; }}
    .email-form button {{ background: #27AE60; color: #fff; border: none; padding: 0.6rem 1.2rem; border-radius: 6px; font-weight: 700; cursor: pointer; font-size: 0.9rem; white-space: nowrap; }}
    footer {{ text-align: center; padding: 2.5rem 1rem; color: var(--text-muted); font-size: 0.85rem; border-top: 1px solid var(--border); margin-top: 2rem; background: #fff; }}
    footer a {{ color: var(--blue); }}
    @media (max-width: 600px) {{
      .quick-bar-inner {{ grid-template-columns: 1fr; }}
      .vs-badge {{ display: none; }}
      .card {{ padding: 1.25rem; }}
    }}
  </style>
</head>
<body>

<nav>
  <a href="../">🔍 OS Alternative Finder</a>
  <span class="sep">/</span>
  <a href="../{category_slug}/">{category_label}</a>
  <span class="sep">/</span>
  <span style="color:#fff;opacity:0.7">{title}</span>
</nav>

<div class="hero">
  <div class="category-badge">{category_icon} {category_label}</div>
  <h1>{title}</h1>
  <p class="subtitle">Detailed comparison: pricing, data ownership, features, migration path, and which is right for you.</p>
  <div class="hero-badges">
    <span class="hero-badge">✅ Free Alternative: {oss_pricing}</span>
    <span class="hero-badge">🔓 Open Source</span>
    <span class="hero-badge">🤖 AI-Analyzed</span>
    <span class="hero-badge">📅 {updated}</span>
  </div>
</div>

<div class="quick-bar">
  <div class="quick-bar-inner">
    <div class="qb-tool proprietary">
      <div class="label">Proprietary</div>
      <div class="name">{prop_name}</div>
      <div class="price">{prop_pricing}</div>
      <a href="{prop_affiliate}" target="_blank" rel="noopener sponsored" class="visit-btn">Visit {prop_name} →</a>
    </div>
    <div class="vs-badge">VS</div>
    <div class="qb-tool opensource">
      <div class="label">Open Source ✅</div>
      <div class="name">{oss_name}</div>
      <div class="price">{oss_pricing}</div>
      <a href="{oss_website}" target="_blank" rel="noopener" class="visit-btn">Visit {oss_name} →</a>
    </div>
  </div>
</div>

<div class="content">

  {carbon_ad}

  <div class="card">
    {body}
  </div>

  {adsense_unit}

  {github_box}

  <!-- EMAIL CAPTURE -->
  <div class="email-box">
    <h3>🔔 Get Weekly Open Source Picks</h3>
    <p>New tool comparisons, self-hosting guides, and money-saving alternatives — every week.</p>
    <div class="email-form">
      <input type="email" placeholder="your@email.com" aria-label="Email address">
      <button onclick="handleSubscribe(this)">Subscribe Free</button>
    </div>
  </div>

  <!-- RELATED COMPARISONS -->
  {related_section}

  <div class="card" style="text-align:center; padding: 1.5rem;">
    <p style="font-size:0.9rem; color:#718096; margin-bottom:1rem;">Found this helpful? Explore all comparisons.</p>
    <a href="../" style="display:inline-block; background:var(--blue); color:#fff; padding:0.65rem 1.75rem; border-radius:6px; text-decoration:none; font-weight:600; font-size:0.9rem;">← View All Comparisons</a>
  </div>
</div>

<footer>
  Open Source Alternative Finder &nbsp;·&nbsp; Powered by free AI APIs &nbsp;·&nbsp;
  Hosted on <a href="https://pages.github.com">GitHub Pages</a> &nbsp;·&nbsp; $0/month to operate<br>
  <span style="font-size:0.8rem; opacity:0.7">Content is AI-generated for informational purposes. Verify all details at official websites before making purchasing decisions.</span>
</footer>

<script>
function handleSubscribe(btn) {{
  const input = btn.previousElementSibling;
  const email = input.value.trim();
  if (!email || !email.includes('@')) {{ input.style.outline='2px solid red'; return; }}
  btn.textContent = '✅ Subscribed!';
  btn.style.background = '#1A7A3F';
  input.value = '';
  // TODO: connect to your email provider (Mailchimp, ConvertKit, etc.)
  // fetch('/api/subscribe', {{method:'POST', body: JSON.stringify({{email}})}})
}}
</script>

</body>
</html>"""


# ── INDEX PAGE TEMPLATE ───────────────────────────────────────────────────────
INDEX_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <!-- SEO -->
  <title>Open Source Alternative Finder — Free Replacements for Popular Paid Tools</title>
  <meta name="description" content="Discover free, open-source alternatives to Slack, Notion, Figma, Jira, Dropbox and more. AI-powered comparisons updated daily. Save thousands per year.">
  <meta name="keywords" content="open source alternatives, free software alternatives, self-hosted tools, slack alternative, notion alternative, figma alternative">
  <link rel="canonical" href="{site_base_url}/">
  <meta name='impact-site-verification' value='e966ad45-df5a-41e8-9d33-b8f8527e8f93'>
  <meta name="google-site-verification" content="{google_verification}">
  <meta name="robots" content="index, follow">

  <!-- Open Graph -->
  <meta property="og:type" content="website">
  <meta property="og:title" content="Open Source Alternative Finder">
  <meta property="og:description" content="Find free, open-source replacements for popular paid tools. AI-powered comparisons updated daily.">
  <meta property="og:url" content="{site_base_url}/">
  <meta property="og:site_name" content="Open Source Alternative Finder">

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="Open Source Alternative Finder">
  <meta name="twitter:description" content="Find free, open-source replacements for Slack, Notion, Figma, and more.">

  <!-- Schema.org -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "Open Source Alternative Finder",
    "url": "{site_base_url}/",
    "description": "AI-powered comparisons of open-source alternatives to popular paid software",
    "potentialAction": {{
      "@type": "SearchAction",
      "target": "{site_base_url}/?q={{search_term_string}}",
      "query-input": "required name=search_term_string"
    }}
  }}
  </script>

  {adsense_script}
  <link rel="icon" href="favicon.ico" type="image/x-icon">
  <style>
    :root {{ --blue: #1F5C99; --blue-light: #2980B9; --green: #1A7A3F; --bg: #F0F4F8; --card: #fff; --border: #E2E8F0; --text: #1A202C; --text-muted: #718096; }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
    .hero {{ background: linear-gradient(135deg, var(--blue) 0%, var(--blue-light) 100%); color: #fff; padding: 4rem 1.5rem 3rem; text-align: center; }}
    .hero h1 {{ font-size: clamp(2rem, 5vw, 3rem); font-weight: 900; margin-bottom: 0.75rem; }}
    .hero p {{ opacity: 0.88; font-size: 1.1rem; max-width: 580px; margin: 0 auto 2rem; }}
    .hero-stats {{ display: flex; gap: 2rem; justify-content: center; flex-wrap: wrap; }}
    .stat {{ text-align: center; }}
    .stat .num {{ font-size: 2rem; font-weight: 900; }}
    .stat .label {{ font-size: 0.82rem; opacity: 0.8; text-transform: uppercase; letter-spacing: 0.05em; }}
    /* Search bar */
    .search-bar {{ background: #fff; border-bottom: 1px solid var(--border); padding: 1rem 1.5rem; }}
    .search-bar-inner {{ max-width: 1200px; margin: 0 auto; display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }}
    .search-input {{ flex: 1; padding: 0.55rem 1rem; border: 2px solid var(--border); border-radius: 8px; font-size: 0.9rem; min-width: 200px; }}
    .search-input:focus {{ outline: none; border-color: var(--blue); }}
    .filter-btn {{ padding: 0.4rem 1rem; border-radius: 20px; border: 2px solid var(--border); background: #fff; cursor: pointer; font-size: 0.82rem; font-weight: 600; color: var(--text-muted); transition: all 0.15s; }}
    .filter-btn:hover, .filter-btn.active {{ background: var(--blue); color: #fff; border-color: var(--blue); }}
    .filter-label {{ font-size: 0.82rem; font-weight: 700; color: var(--text-muted); white-space: nowrap; }}
    .grid {{ max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem; display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1.5rem; }}
    .card {{ background: var(--card); border-radius: 12px; border: 1px solid var(--border); overflow: hidden; transition: transform 0.2s, box-shadow 0.2s; display: flex; flex-direction: column; }}
    .card:hover {{ transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,0.12); }}
    .card-category {{ padding: 0.5rem 1rem; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: #fff; }}
    .card-body {{ padding: 1.25rem 1.25rem 0.75rem; flex: 1; }}
    .vs-line {{ display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.5rem; }}
    .vs-line .tool-name {{ font-weight: 700; font-size: 1.05rem; }}
    .vs-line .vs {{ font-size: 0.72rem; font-weight: 900; color: var(--text-muted); background: #F0F4F8; padding: 0.2rem 0.5rem; border-radius: 4px; }}
    .savings {{ display: flex; align-items: center; gap: 0.75rem; margin: 0.75rem 0; padding: 0.6rem 0.75rem; background: #EAFAF1; border-radius: 6px; border: 1px solid #A9DFBF; }}
    .savings .label {{ font-size: 0.75rem; color: var(--text-muted); }}
    .savings .value {{ font-size: 0.88rem; font-weight: 700; color: var(--green); }}
    .card-footer {{ padding: 0.75rem 1.25rem 1.25rem; }}
    .cta {{ display: block; text-align: center; background: var(--blue); color: #fff; padding: 0.6rem 1rem; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 0.88rem; transition: background 0.15s; }}
    .cta:hover {{ background: var(--blue-light); }}
    .no-results {{ text-align: center; padding: 3rem; color: var(--text-muted); display: none; }}
    footer {{ text-align: center; padding: 3rem 1rem 2rem; color: var(--text-muted); font-size: 0.85rem; border-top: 1px solid var(--border); background: #fff; margin-top: 1rem; }}
    footer a {{ color: var(--blue); }}
    @media (max-width: 600px) {{
      .grid {{ grid-template-columns: 1fr; padding: 1rem; }}
      .hero {{ padding: 2.5rem 1rem 2rem; }}
    }}
  </style>
</head>
<body>

<div class="hero">
  <h1>🔍 Open Source Alternative Finder</h1>
  <p>Discover free, open-source replacements for popular paid tools — with detailed AI-powered comparisons. Save thousands per year.</p>
  <div class="hero-stats">
    <div class="stat"><div class="num">{total_comparisons}</div><div class="label">Comparisons</div></div>
    <div class="stat"><div class="num">{total_tools}</div><div class="label">Tools Covered</div></div>
    <div class="stat"><div class="num">$0</div><div class="label">Cost to Run</div></div>
    <div class="stat"><div class="num">Daily</div><div class="label">Auto-Updated</div></div>
  </div>
</div>

<div class="search-bar">
  <div class="search-bar-inner">
    <input class="search-input" type="search" placeholder="🔎  Search tools... (e.g. Slack, Notion, Figma)" oninput="handleSearch(this.value)" aria-label="Search comparisons">
    <span class="filter-label">Filter:</span>
    <button class="filter-btn active" onclick="filterCards('all', this)">All</button>
    {filter_buttons}
  </div>
</div>

<div class="grid" id="card-grid">
{cards}
</div>
<div class="no-results" id="no-results">No comparisons found. Try a different search term.</div>

<footer>
  <strong>Open Source Alternative Finder</strong><br>
  Powered by <a href="https://groq.com">Groq</a> + <a href="https://ai.google.dev">Gemini</a> APIs &nbsp;·&nbsp;
  Hosted on <a href="https://pages.github.com">GitHub Pages</a> &nbsp;·&nbsp;
  <a href="https://github.com/aiopentec/opensource-alternative-finder">View Source on GitHub</a><br>
  <span style="font-size:0.8rem; opacity:0.7">Updated {updated} &nbsp;·&nbsp; $0/month to operate &nbsp;·&nbsp; Content for informational purposes only</span>
</footer>

<script>
let activeCategory = 'all';

function filterCards(category, btn) {{
  activeCategory = category;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  applyFilters();
}}

function handleSearch(query) {{
  applyFilters(query.toLowerCase());
}}

function applyFilters(query) {{
  const q = query || document.querySelector('.search-input').value.toLowerCase();
  let visible = 0;
  document.querySelectorAll('#card-grid .card').forEach(card => {{
    const matchCat = activeCategory === 'all' || card.dataset.category === activeCategory;
    const matchQ   = !q || card.dataset.search.includes(q);
    card.style.display = (matchCat && matchQ) ? '' : 'none';
    if (matchCat && matchQ) visible++;
  }});
  document.getElementById('no-results').style.display = visible === 0 ? 'block' : 'none';
}}
</script>

</body>
</html>"""


GITHUB_BOX = """
  <div class="card" style="background: linear-gradient(135deg, #1a1a2e, #16213e); color:#fff; border-color:#333;">
    <div style="display:flex; align-items:center; gap:1rem; flex-wrap:wrap;">
      <div style="font-size:2.5rem;">📦</div>
      <div>
        <div style="font-weight:700; font-size:1.05rem; margin-bottom:0.25rem;">{oss_name} on GitHub</div>
        <a href="https://github.com/{github_repo}" target="_blank" rel="noopener" style="color:#63B3ED; font-size:0.9rem;">github.com/{github_repo}</a>
        <div style="font-size:0.82rem; color:#A0AEC0; margin-top:0.25rem;">⭐ ~{stars} stars &nbsp;·&nbsp; Free to self-host &nbsp;·&nbsp; Open Source</div>
      </div>
      <a href="https://github.com/{github_repo}" target="_blank" rel="noopener" style="margin-left:auto; background:#238636; color:#fff; padding:0.5rem 1.25rem; border-radius:6px; text-decoration:none; font-weight:600; font-size:0.88rem;">View on GitHub →</a>
    </div>
  </div>"""


def build_related_section(current_slug: str, current_prop: str, current_oss: str,
                           all_comparisons: List[Dict]) -> str:
    """Find comparisons that share a tool with the current page."""
    related = []
    for c in all_comparisons:
        if c['slug'] == current_slug:
            continue
        if (c.get('proprietary_tool') == current_prop or
            c.get('oss_tool') == current_oss or
            c.get('proprietary_tool') == current_oss or
            c.get('oss_tool') == current_prop):
            related.append(c)
    if not related:
        return ''
    links = ''.join(
        f'<a class="related-link" href="../{c["slug"]}/">{c["title"]}</a>'
        for c in related[:6]
    )
    return f"""
  <div class="card">
    <h2 style="font-size:1rem; font-weight:700; color:#1F5C99; margin-bottom:0.75rem;">🔗 Related Comparisons</h2>
    <div class="related-grid">{links}</div>
  </div>"""


def build_sitemap(all_comparisons: List[Dict], site_dir: str, categories: List[str]):
    """Generate sitemap.xml for Google Search Console."""
    today = datetime.utcnow().strftime('%Y-%m-%d')
    urls = [f'  <url><loc>{SITE_BASE_URL}/</loc><changefreq>daily</changefreq><priority>1.0</priority><lastmod>{today}</lastmod></url>']
    for cat in categories:
        urls.append(f'  <url><loc>{SITE_BASE_URL}/{cat}/</loc><changefreq>weekly</changefreq><priority>0.7</priority><lastmod>{today}</lastmod></url>')
    for comp in all_comparisons:
        urls.append(f'  <url><loc>{SITE_BASE_URL}/{comp["slug"]}/</loc><changefreq>weekly</changefreq><priority>0.9</priority><lastmod>{today}</lastmod></url>')
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += '\n'.join(urls) + '\n</urlset>'
    with open(Path(site_dir) / 'sitemap.xml', 'w') as f:
        f.write(sitemap)
    logger.info(f"   🗺️  sitemap.xml ({len(all_comparisons) + len(categories) + 1} URLs)")


def build_404_page(site_dir: str):
    """GitHub Pages serves 404.html for missing pages."""
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Page Not Found | Open Source Alternative Finder</title>
<style>body{{font-family:system-ui,sans-serif;text-align:center;padding:4rem 1rem;background:#F0F4F8;}}
h1{{font-size:3rem;color:#1F5C99;}}p{{color:#718096;margin:1rem 0 2rem;}}
a{{display:inline-block;background:#1F5C99;color:#fff;padding:0.65rem 1.5rem;border-radius:6px;text-decoration:none;font-weight:600;}}
</style></head>
<body>
<h1>404</h1>
<p>Oops — this page doesn't exist. The comparison you're looking for may have moved.</p>
<a href="{SITE_BASE_URL}/">← Back to All Comparisons</a>
</body></html>"""
    with open(Path(site_dir) / '404.html', 'w') as f:
        f.write(html)


def build_site(cache_dir: str = '.cache/publish', site_dir: str = 'site'):
    Path(site_dir).mkdir(parents=True, exist_ok=True)

    all_comparisons: List[Dict] = []
    for json_file in sorted(Path(cache_dir).glob('comparisons_*.json')):
        with open(json_file) as f:
            all_comparisons.extend(json.load(f))

    if not all_comparisons:
        logger.warning("⚠️  No comparisons found in .cache/publish/")
        return

    logger.info(f"📦 Building site from {len(all_comparisons)} comparisons...")
    updated   = datetime.utcnow().strftime('%B %d, %Y')
    iso_date  = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    data_dir = Path(site_dir) / 'data'
    data_dir.mkdir(exist_ok=True)
    with open(data_dir / 'comparisons.json', 'w') as f:
        json.dump(all_comparisons, f, indent=2)

    categories = sorted(set(c.get('category', 'general') for c in all_comparisons))
    unique_tools = set()
    for c in all_comparisons:
        unique_tools.add(c.get('proprietary_tool', ''))
        unique_tools.add(c.get('oss_tool', ''))

    cards_html = ''
    category_page_counts = {}
    adsense_script = get_adsense_snippet()
    adsense_unit   = get_adsense_unit()
    carbon_ad      = get_carbon_ad()

    for comp in all_comparisons:
        slug        = comp['slug']
        category    = comp.get('category', 'general')
        cat_icon    = CATEGORY_ICONS.get(category, '🔧')
        cat_color   = CATEGORY_COLORS.get(category, '#95A5A6')
        cat_label   = category.replace('-', ' ').title()
        prop_key    = comp.get('proprietary_key', '')
        oss_key     = comp.get('oss_key', '')
        prop_name   = comp.get('proprietary_tool', '')
        oss_name    = comp.get('oss_tool', '')
        canonical   = f"{SITE_BASE_URL}/{slug}/"

        seo_title   = f"{prop_name} vs {oss_name} ({updated}) — Free Open Source Alternative"
        seo_desc    = (f"Is {oss_name} a good free alternative to {prop_name}? "
                       f"Detailed comparison of pricing, features, data ownership, and migration. "
                       f"Save {comp.get('proprietary_pricing','money')} by switching.")

        page_dir = Path(site_dir) / slug
        page_dir.mkdir(parents=True, exist_ok=True)

        body_html = markdown_to_html(comp.get('comparison_markdown', ''))

        github_box_html = ''
        if comp.get('oss_github'):
            github_box_html = GITHUB_BOX.format(
                oss_name=oss_name,
                github_repo=comp['oss_github'],
                stars=comp.get('oss_stars', 'N/A')
            )

        related_html = build_related_section(slug, prop_name, oss_name, all_comparisons)

        page_html = COMPARISON_PAGE.format(
            title=comp['title'],
            seo_title=seo_title,
            seo_description=seo_desc,
            canonical_url=canonical,
            site_base_url=SITE_BASE_URL,
            iso_date=iso_date,
            category_slug=category,
            category_label=cat_label,
            category_icon=cat_icon,
            category_color=cat_color,
            updated=updated,
            prop_name=prop_name,
            prop_pricing=comp.get('proprietary_pricing', 'N/A'),
            prop_affiliate=AFFILIATE_LINKS.get(prop_key, comp.get('proprietary_website', '#')),
            oss_name=oss_name,
            oss_pricing=comp.get('oss_pricing', 'Free'),
            oss_website=AFFILIATE_LINKS.get(oss_key, comp.get('oss_website', '#')),
            body=body_html,
            github_box=github_box_html,
            related_section=related_html,
            adsense_script=adsense_script,
            adsense_unit=adsense_unit,
            carbon_ad=carbon_ad,
        )
        with open(page_dir / 'index.html', 'w') as f:
            f.write(page_html)

        category_page_counts[category] = category_page_counts.get(category, 0) + 1

        # Search data attributes for live filtering
        search_data = f"{prop_name} {oss_name} {cat_label}".lower()
        cards_html += f"""
  <div class="card" data-category="{category}" data-search="{search_data}">
    <div class="card-category" style="background:{cat_color}">{cat_icon} {cat_label}</div>
    <div class="card-body">
      <div class="vs-line">
        <span class="tool-name" style="color:#C0392B">{prop_name}</span>
        <span class="vs">VS</span>
        <span class="tool-name" style="color:{cat_color}">{oss_name}</span>
      </div>
      <div class="savings">
        <span class="label">💰 Switch and save:</span>
        <span class="value">{comp.get('proprietary_pricing', 'N/A')} → {comp.get('oss_pricing', 'Free')}</span>
      </div>
    </div>
    <div class="card-footer">
      <a class="cta" href="{slug}/">Compare Now →</a>
    </div>
  </div>"""

    # Category index pages
    for category in categories:
        cat_comps = [c for c in all_comparisons if c.get('category', 'general') == category]
        cat_dir = Path(site_dir) / category
        cat_dir.mkdir(exist_ok=True)
        cat_cards = '\n'.join(
            f'<li><a href="../{c["slug"]}/">{c["title"]}</a> — {c.get("oss_pricing","Free")}</li>'
            for c in cat_comps
        )
        cat_page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{category.replace('-',' ').title()} Open Source Alternatives | OS Alternative Finder</title>
<meta name="description" content="Free open-source alternatives to popular {category.replace('-',' ')} tools. Detailed comparisons with pricing and migration guides.">
<link rel="canonical" href="{SITE_BASE_URL}/{category}/">
<style>body{{font-family:system-ui,sans-serif;max-width:800px;margin:2rem auto;padding:0 1rem;}}a{{color:#1F5C99;}}</style></head>
<body><h1>{CATEGORY_ICONS.get(category,'🔧')} {category.replace('-',' ').title()} Comparisons</h1>
<p><a href="../">← All categories</a></p><ul style="margin:1.5rem 0 0 1.5rem;line-height:2.2">{cat_cards}</ul>
<footer style="margin-top:3rem;color:#888;font-size:0.85rem;border-top:1px solid #eee;padding-top:1rem">
Open Source Alternative Finder · Updated {updated}</footer></body></html>"""
        with open(cat_dir / 'index.html', 'w') as f:
            f.write(cat_page)

    filter_buttons = '\n'.join(
        f'<button class="filter-btn" onclick="filterCards(\'{cat}\', this)">{CATEGORY_ICONS.get(cat,"🔧")} {cat.replace("-"," ").title()} ({category_page_counts.get(cat, 0)})</button>'
        for cat in categories
    )

    index_html = INDEX_PAGE.format(
        total_comparisons=len(all_comparisons),
        total_tools=len(unique_tools),
        updated=updated,
        site_base_url=SITE_BASE_URL,
        filter_buttons=filter_buttons,
        cards=cards_html,
        adsense_script=adsense_script,
        # ── CHANGED: hardcoded verification code as fallback ──────────────────
        google_verification=os.getenv("GOOGLE_SITE_VERIFICATION", "sgWLzv3yQVjDBJUjSqkzfFW2WDtfpWNMzQ-_pEw9sqQ"),
        # ─────────────────────────────────────────────────────────────────────
    )
    with open(Path(site_dir) / 'index.html', 'w') as f:
        f.write(index_html)

    # Extra files
    with open(Path(site_dir) / 'favicon.ico', 'wb') as f:
        f.write(b'')
    with open(Path(site_dir) / 'CNAME.example', 'w') as f:
        f.write("# Rename to CNAME and add your custom domain, e.g.: alternatives.yourdomain.com\n")
    with open(Path(site_dir) / 'robots.txt', 'w') as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE_URL}/sitemap.xml\n")

    build_sitemap(all_comparisons, site_dir, categories)
    build_404_page(site_dir)

    logger.info(f"✅ Site built successfully!")
    logger.info(f"   📄 {len(all_comparisons)} comparison pages")
    logger.info(f"   🗂️  {len(categories)} category pages")
    logger.info(f"   🏠 index.html + 404.html")
    logger.info(f"   🗺️  sitemap.xml")
    logger.info(f"   📁 Output: {site_dir}/")


if __name__ == "__main__":
    build_site()
