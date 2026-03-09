#!/usr/bin/env python3
"""
publish_github_pages.py
Converts generated JSON comparisons into a complete static website.
GitHub Pages serves the output for free.

Usage: python scripts/publish_github_pages.py
"""

import json, logging, re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)

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


def markdown_to_html(md: str) -> str:
    """Convert Markdown to HTML. Handles the output format from our AI prompts."""
    try:
        import markdown as md_lib
        return md_lib.markdown(md, extensions=['tables', 'nl2br'])
    except ImportError:
        pass

    html = md
    # Headers
    html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$',  r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$',   r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$',    r'<h1>\1</h1>', html, flags=re.MULTILINE)
    # Bold / italic
    html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', html)
    html = re.sub(r'\*\*(.+?)\*\*',     r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*',         r'<em>\1</em>', html)
    # Inline code
    html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)
    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', html)
    # Blockquote
    html = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)

    # Tables
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

    # Bullet lists
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
    # HR
    html = html.replace('---', '<hr>')
    # Paragraphs (double newline = paragraph break)
    paras = re.split(r'\n{2,}', html)
    wrapped = []
    for p in paras:
        p = p.strip()
        if p and not re.match(r'^<(h[1-6]|ul|ol|table|div|blockquote|hr)', p):
            p = f'<p>{p}</p>'
        wrapped.append(p)
    return '\n'.join(wrapped)


# NOTE: All links use relative paths (../) so the site works correctly
# when hosted in a subdirectory on GitHub Pages, e.g.:
# https://username.github.io/opensource-alternative-finder/

COMPARISON_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | Open Source Alternatives</title>
  <meta name="description" content="Detailed comparison: {title}. Pricing, features, migration guide, and when to choose each.">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="Free open-source alternative finder. Compare {title}.">
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

    /* NAV */
    nav {{ background: var(--blue); padding: 0.75rem 1.5rem; display: flex; align-items: center; gap: 1rem; }}
    nav a {{ color: #fff; text-decoration: none; font-size: 0.9rem; opacity: 0.9; }}
    nav a:hover {{ opacity: 1; }}
    nav .sep {{ color: rgba(255,255,255,0.4); }}

    /* HERO */
    .hero {{ background: linear-gradient(135deg, var(--blue) 0%, var(--blue-light) 100%); color: #fff; padding: 3rem 1.5rem 2.5rem; text-align: center; }}
    .hero .category-badge {{ display: inline-block; background: var(--category); color: #fff; font-size: 0.75rem; font-weight: 700; padding: 0.3rem 0.9rem; border-radius: 20px; margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    .hero h1 {{ font-size: clamp(1.6rem, 4vw, 2.4rem); font-weight: 800; margin-bottom: 0.75rem; }}
    .hero .subtitle {{ opacity: 0.85; font-size: 1rem; max-width: 600px; margin: 0 auto 1.5rem; }}
    .hero-badges {{ display: flex; gap: 0.75rem; justify-content: center; flex-wrap: wrap; }}
    .hero-badge {{ background: rgba(255,255,255,0.18); border: 1px solid rgba(255,255,255,0.3); padding: 0.35rem 0.9rem; border-radius: 20px; font-size: 0.82rem; backdrop-filter: blur(4px); }}

    /* QUICK COMPARE BAR */
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
    .vs-badge {{ font-size: 1.3rem; font-weight: 900; color: var(--blue); }}

    /* CONTENT */
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

    /* TABLES */
    .table-wrapper {{ overflow-x: auto; margin: 1rem 0; border-radius: 8px; border: 1px solid var(--border); }}
    table {{ width: 100%; border-collapse: collapse; }}
    thead th {{ background: var(--blue); color: #fff; padding: 0.7rem 1rem; text-align: left; font-size: 0.88rem; font-weight: 600; }}
    tbody td {{ padding: 0.65rem 1rem; border-bottom: 1px solid var(--border); font-size: 0.9rem; }}
    tbody tr:last-child td {{ border-bottom: none; }}
    tbody tr:nth-child(even) td {{ background: #F8FAFC; }}

    /* FOOTER */
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
  <p class="subtitle">Side-by-side comparison: pricing, features, migration guide, and which tool is right for you.</p>
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
    </div>
    <div class="vs-badge">VS</div>
    <div class="qb-tool opensource">
      <div class="label">Open Source</div>
      <div class="name">{oss_name}</div>
      <div class="price">{oss_pricing}</div>
    </div>
  </div>
</div>

<div class="content">
  <div class="card">
    {body}
  </div>

  {github_box}

  <div class="card" style="text-align:center; padding: 1.5rem;">
    <p style="font-size:0.9rem; color:#718096; margin-bottom:1rem;">Found this helpful? Explore more comparisons.</p>
    <a href="../" style="display:inline-block; background:var(--blue); color:#fff; padding:0.65rem 1.75rem; border-radius:6px; text-decoration:none; font-weight:600; font-size:0.9rem;">← View All Comparisons</a>
  </div>
</div>

<footer>
  Open Source Alternative Finder &nbsp;·&nbsp; Powered by free AI APIs &nbsp;·&nbsp; Hosted on <a href="https://pages.github.com">GitHub Pages</a> &nbsp;·&nbsp; $0/month to operate<br>
  <span style="font-size:0.8rem; opacity:0.7">Content is AI-generated for informational purposes. Verify all details at official websites before making purchasing decisions.</span>
</footer>

</body>
</html>"""


INDEX_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Open Source Alternative Finder — Free Tool Comparisons</title>
  <meta name="description" content="Find free, open-source alternatives to popular paid software. AI-powered comparisons updated daily.">
  <link rel="icon" href="favicon.ico" type="image/x-icon">
  <style>
    :root {{ --blue: #1F5C99; --blue-light: #2980B9; --green: #1A7A3F; --bg: #F0F4F8; --card: #fff; --border: #E2E8F0; --text: #1A202C; --text-muted: #718096; }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}

    /* HERO */
    .hero {{ background: linear-gradient(135deg, var(--blue) 0%, var(--blue-light) 100%); color: #fff; padding: 4rem 1.5rem 3rem; text-align: center; }}
    .hero h1 {{ font-size: clamp(2rem, 5vw, 3rem); font-weight: 900; margin-bottom: 0.75rem; }}
    .hero p {{ opacity: 0.88; font-size: 1.1rem; max-width: 580px; margin: 0 auto 2rem; }}
    .hero-stats {{ display: flex; gap: 2rem; justify-content: center; flex-wrap: wrap; }}
    .stat {{ text-align: center; }}
    .stat .num {{ font-size: 2rem; font-weight: 900; }}
    .stat .label {{ font-size: 0.82rem; opacity: 0.8; text-transform: uppercase; letter-spacing: 0.05em; }}

    /* FILTER BAR */
    .filter-bar {{ background: #fff; border-bottom: 1px solid var(--border); padding: 1rem 1.5rem; position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
    .filter-bar-inner {{ max-width: 1200px; margin: 0 auto; display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }}
    .filter-btn {{ padding: 0.4rem 1rem; border-radius: 20px; border: 2px solid var(--border); background: #fff; cursor: pointer; font-size: 0.82rem; font-weight: 600; color: var(--text-muted); transition: all 0.15s; }}
    .filter-btn:hover, .filter-btn.active {{ background: var(--blue); color: #fff; border-color: var(--blue); }}
    .filter-label {{ font-size: 0.82rem; font-weight: 700; color: var(--text-muted); margin-right: 0.25rem; }}

    /* GRID */
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

    /* FOOTER */
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
  <p>Discover free, open-source replacements for popular paid tools — with detailed AI-powered comparisons.</p>
  <div class="hero-stats">
    <div class="stat"><div class="num">{total_comparisons}</div><div class="label">Comparisons</div></div>
    <div class="stat"><div class="num">{total_tools}</div><div class="label">Tools Covered</div></div>
    <div class="stat"><div class="num">$0</div><div class="label">Cost to Run</div></div>
    <div class="stat"><div class="num">Daily</div><div class="label">Auto-Updated</div></div>
  </div>
</div>

<div class="filter-bar">
  <div class="filter-bar-inner">
    <span class="filter-label">Filter:</span>
    <button class="filter-btn active" onclick="filterCards('all')">All</button>
    {filter_buttons}
  </div>
</div>

<div class="grid" id="card-grid">
{cards}
</div>

<footer>
  <strong>Open Source Alternative Finder</strong><br>
  Powered by <a href="https://groq.com">Groq</a> + <a href="https://ai.google.dev">Gemini</a> APIs &nbsp;·&nbsp;
  Hosted on <a href="https://pages.github.com">GitHub Pages</a> &nbsp;·&nbsp;
  <a href="https://github.com/YOUR-USERNAME/opensource-alternative-finder">View Source</a><br>
  <span style="font-size:0.8rem; opacity:0.7">Updated {updated} &nbsp;·&nbsp; $0/month to operate &nbsp;·&nbsp; Content for informational purposes only</span>
</footer>

<script>
function filterCards(category) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  document.querySelectorAll('#card-grid .card').forEach(card => {{
    card.style.display = (category === 'all' || card.dataset.category === category) ? '' : 'none';
  }});
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


def build_site(cache_dir: str = '.cache/publish', site_dir: str = 'site'):
    Path(site_dir).mkdir(parents=True, exist_ok=True)

    # Load all comparisons
    all_comparisons: List[Dict] = []
    for json_file in sorted(Path(cache_dir).glob('comparisons_*.json')):
        with open(json_file) as f:
            all_comparisons.extend(json.load(f))

    if not all_comparisons:
        logger.warning("⚠️  No comparisons found in .cache/publish/")
        return

    logger.info(f"📦 Building site from {len(all_comparisons)} comparisons...")
    updated = datetime.utcnow().strftime('%B %d, %Y')

    # Save raw data
    data_dir = Path(site_dir) / 'data'
    data_dir.mkdir(exist_ok=True)
    with open(data_dir / 'comparisons.json', 'w') as f:
        json.dump(all_comparisons, f, indent=2)

    # Collect categories
    categories = sorted(set(c.get('category', 'general') for c in all_comparisons))
    unique_tools = set()
    for c in all_comparisons:
        unique_tools.add(c.get('proprietary_tool', ''))
        unique_tools.add(c.get('oss_tool', ''))

    # Build individual pages
    cards_html = ''
    category_page_counts = {}

    for comp in all_comparisons:
        slug      = comp['slug']
        category  = comp.get('category', 'general')
        cat_icon  = CATEGORY_ICONS.get(category, '🔧')
        cat_color = CATEGORY_COLORS.get(category, '#95A5A6')
        cat_label = category.replace('-', ' ').title()

        page_dir = Path(site_dir) / slug
        page_dir.mkdir(parents=True, exist_ok=True)

        body_html = markdown_to_html(comp.get('comparison_markdown', ''))

        # GitHub box
        github_box_html = ''
        if comp.get('oss_github'):
            github_box_html = GITHUB_BOX.format(
                oss_name=comp['oss_tool'],
                github_repo=comp['oss_github'],
                stars=comp.get('oss_stars', 'N/A')
            )

        page_html = COMPARISON_PAGE.format(
            title=comp['title'],
            category_slug=category,
            category_label=cat_label,
            category_icon=cat_icon,
            category_color=cat_color,
            updated=updated,
            prop_name=comp.get('proprietary_tool', ''),
            prop_pricing=comp.get('proprietary_pricing', 'N/A'),
            oss_name=comp.get('oss_tool', ''),
            oss_pricing=comp.get('oss_pricing', 'Free'),
            body=body_html,
            github_box=github_box_html
        )
        with open(page_dir / 'index.html', 'w') as f:
            f.write(page_html)

        category_page_counts[category] = category_page_counts.get(category, 0) + 1

        # Build index card — relative path from index.html to slug/
        cards_html += f"""
  <div class="card" data-category="{category}">
    <div class="card-category" style="background:{cat_color}">{cat_icon} {cat_label}</div>
    <div class="card-body">
      <div class="vs-line">
        <span class="tool-name" style="color:#C0392B">{comp['proprietary_tool']}</span>
        <span class="vs">VS</span>
        <span class="tool-name" style="color:{cat_color}">{comp['oss_tool']}</span>
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

    # Build category index pages
    for category in categories:
        cat_comps = [c for c in all_comparisons if c.get('category', 'general') == category]
        cat_dir = Path(site_dir) / category
        cat_dir.mkdir(exist_ok=True)
        # Links go up one level (../) to reach individual comparison pages
        cat_cards = '\n'.join(
            f'<li><a href="../{c["slug"]}/">{c["title"]}</a> — {c.get("oss_pricing","Free")}</li>'
            for c in cat_comps
        )
        cat_page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{category.replace('-',' ').title()} Tools — Open Source Alternatives</title>
<style>body{{font-family:system-ui,sans-serif;max-width:800px;margin:2rem auto;padding:0 1rem;}}a{{color:#1F5C99;}}</style></head>
<body><h1>{CATEGORY_ICONS.get(category,'🔧')} {category.replace('-',' ').title()} Comparisons</h1>
<p><a href="../">← All categories</a></p><ul style="margin:1.5rem 0 0 1.5rem;line-height:2.2">{cat_cards}</ul>
<footer style="margin-top:3rem;color:#888;font-size:0.85rem;border-top:1px solid #eee;padding-top:1rem">
Open Source Alternative Finder · Updated {updated}</footer></body></html>"""
        with open(cat_dir / 'index.html', 'w') as f:
            f.write(cat_page)

    # Filter buttons for index
    filter_buttons = '\n'.join(
        f'<button class="filter-btn" onclick="filterCards(\'{cat}\')">{CATEGORY_ICONS.get(cat,"🔧")} {cat.replace("-"," ").title()} ({category_page_counts.get(cat, 0)})</button>'
        for cat in categories
    )

    # Build index page
    index_html = INDEX_PAGE.format(
        total_comparisons=len(all_comparisons),
        total_tools=len(unique_tools),
        updated=updated,
        filter_buttons=filter_buttons,
        cards=cards_html
    )
    with open(Path(site_dir) / 'index.html', 'w') as f:
        f.write(index_html)

    # Write a minimal favicon placeholder
    with open(Path(site_dir) / 'favicon.ico', 'wb') as f:
        f.write(b'')

    # Write CNAME placeholder (user fills in their domain)
    with open(Path(site_dir) / 'CNAME.example', 'w') as f:
        f.write("# Rename this file to CNAME and put your custom domain here\n# e.g.: alternatives.yourdomain.com\n")

    # Write robots.txt
    with open(Path(site_dir) / 'robots.txt', 'w') as f:
        f.write("User-agent: *\nAllow: /\n")

    logger.info(f"✅ Site built successfully!")
    logger.info(f"   📄 {len(all_comparisons)} comparison pages")
    logger.info(f"   🗂️  {len(categories)} category index pages")
    logger.info(f"   🏠 1 home page (index.html)")
    logger.info(f"   📁 Output: {site_dir}/")


if __name__ == "__main__":
    build_site()
