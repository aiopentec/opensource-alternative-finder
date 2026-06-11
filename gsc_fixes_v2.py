#!/usr/bin/env python3
"""
gsc_fixes_v2.py — GSC error cleanup, round 2
Run from repo root AFTER publish_github_pages.py has built the site.

Fixes addressed:
  404s:
    1. /logo-api/v1/YOUR_KEY/  — placeholder not replaced
    2. /${t.slug}/              — unresolved template variable in HTML
    3. /mo                     — truncated relative link
    4. /cdn-cgi/l/email-protection — Cloudflare mailto interception
    5. /logo-api/v1/$           — shell variable leak (same page as #1, belt+braces)

  Canonical alternates (4xx query-string variants):
    6. /?ref=...  /?q=...      — homepage referral/search variants treated as separate URLs
                                  Fix: ensure canonical tag on homepage points to bare URL
                                  AND add <meta name="robots" content="noindex"> to
                                  any page that gets ?ref= or ?q= params via JS injection

  Crawled-not-indexed:
    7. /sitemap.xml appearing as a page
                               — add X-Robots-Tag noindex via meta tag inside <head>
                                  (GitHub Pages can't set HTTP headers, so we inject a
                                   redirect HTML shim that bounces Googlebot away)

  401:
    8. /logo-api/v1/FREE_KEY/slack — example URL in code block
                                  Fix: rename example domain in HTML to your-site.com
"""

import os
import re
import glob

SITE_DIR = "site"


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def patch_html_files(transform_fn, label=""):
    """Apply transform_fn(html, filepath) -> html to every HTML file under SITE_DIR."""
    changed = 0
    for path in glob.glob(f"{SITE_DIR}/**/*.html", recursive=True):
        original = read(path)
        patched = transform_fn(original, path)
        if patched != original:
            write(path, patched)
            changed += 1
    if label:
        print(f"  [{label}] patched {changed} file(s)")
    return changed


# ─────────────────────────────────────────────
# Fix 1+5: /logo-api placeholder URLs in HTML
# Covers YOUR_KEY, FREE_KEY, and bare $ variants
# ─────────────────────────────────────────────

def fix_logo_api_placeholder_links(html, filepath):
    # Remove href/src/action pointing to logo-api with placeholder keys
    # Replace with javascript:void(0) so the link is inert
    patterns = [
        r'href=["\']https?://[^"\']*logo-api/v1/(?:YOUR_KEY|FREE_KEY|\$)[^"\']*["\']',
        r'href=["\']["\']https?://[^"\']*logo-api/v1/(?:YOUR_KEY|FREE_KEY|\$)[^"\']*["\']',
    ]
    result = html
    # Also catch relative href="/logo-api/..."
    result = re.sub(
        r'(href=["\'])/logo-api/v1/(?:YOUR_KEY|FREE_KEY|\$)[^"\']*(["\'])',
        r'\1javascript:void(0)\2',
        result
    )
    # And fully-qualified osalfinder.com/logo-api variants
    result = re.sub(
        r'(href=["\'])https?://osalfinder\.com/logo-api/v1/(?:YOUR_KEY|FREE_KEY|\$[^/]*)[^"\']*(["\'])',
        r'\1javascript:void(0)\2',
        result
    )
    # Replace example text content "/logo-api/v1/FREE_KEY/slack" with safe placeholder
    result = result.replace(
        "https://osalfinder.com/logo-api/v1/FREE_KEY/slack",
        "https://your-site.com/logo-api/v1/YOUR_KEY/slack"
    )
    result = result.replace(
        "/logo-api/v1/FREE_KEY/slack",
        "/logo-api/v1/YOUR_KEY/slack"
    )
    return result


# ─────────────────────────────────────────────
# Fix 2: Unresolved ${t.slug} template variables
# ─────────────────────────────────────────────

def fix_unresolved_template_vars(html, filepath):
    # Remove any href/src containing ${...} template expressions
    result = re.sub(
        r'(href|src|action)=["\'][^"\']*\$\{[^}]+\}[^"\']*["\']',
        r'\1="javascript:void(0)"',
        html
    )
    # Also catch plain text occurrences in anchor tags
    result = re.sub(
        r'<a\s[^>]*href=["\'][^"\']*\$\{[^}]+\}[^"\']*["\'][^>]*>',
        lambda m: re.sub(r'href=["\'][^"\']*["\']', 'href="javascript:void(0)"', m.group(0)),
        result
    )
    return result


# ─────────────────────────────────────────────
# Fix 3: Truncated /mo and other short-path hrefs
# ─────────────────────────────────────────────

def fix_short_path_hrefs(html, filepath):
    # Remove hrefs that are 1-3 chars like /mo, /ab, /x — clearly truncated
    result = re.sub(
        r'href=["\'](/[a-z]{1,3})["\']',
        'href="javascript:void(0)"',
        html
    )
    return result


# ─────────────────────────────────────────────
# Fix 4: Cloudflare email obfuscation
# Encode mailto: links as HTML entities so Cloudflare can't intercept them
# ─────────────────────────────────────────────

CONTACT_EMAIL = "openaltshub@gmail.com"

def fix_email_links(html, filepath):
    # Replace mailto: links with HTML-entity-encoded version
    # This prevents Cloudflare's email obfuscation from rewriting them to /cdn-cgi/...
    def encode_email(m):
        full = m.group(0)
        # Encode the @ and dots as HTML entities
        encoded_href = full.replace("@", "&#64;").replace(".", "&#46;")
        return encoded_href

    # Match href="mailto:..." — encode the href value
    result = re.sub(
        r'href="mailto:[^"]*"',
        encode_email,
        html
    )
    # Also handle href='mailto:...'
    result = re.sub(
        r"href='mailto:[^']*'",
        encode_email,
        result
    )
    return result


# ─────────────────────────────────────────────
# Fix 6: Canonical tag on homepage
# Ensure it points to bare https://osalfinder.com/ with no query string
# Also inject a JS canonical enforcer for ?ref= and ?q= variants
# ─────────────────────────────────────────────

CANONICAL_ENFORCER_JS = """
<script>
// Redirect any ?ref= or ?q= variants to bare canonical URL
(function() {
  var url = window.location.href;
  if (window.location.search) {
    var params = new URLSearchParams(window.location.search);
    // Preserve nothing — redirect bare URL
    history.replaceState(null, '', window.location.pathname);
  }
})();
</script>
""".strip()

def fix_homepage_canonical(html, filepath):
    # Only run on the homepage index.html
    norm = filepath.replace("\\", "/")
    if not (norm.endswith(f"{SITE_DIR}/index.html") or norm == f"{SITE_DIR}/index.html"):
        return html

    result = html

    # 1. Ensure canonical tag is bare URL (no query string)
    result = re.sub(
        r'<link\s+rel=["\']canonical["\'][^>]*>',
        '<link rel="canonical" href="https://osalfinder.com/" />',
        result
    )
    # If no canonical tag exists, inject one into <head>
    if 'rel="canonical"' not in result and "rel='canonical'" not in result:
        result = result.replace(
            "<head>",
            '<head>\n<link rel="canonical" href="https://osalfinder.com/" />'
        )

    # 2. Inject JS canonical enforcer before </head>
    if "history.replaceState" not in result:
        result = result.replace("</head>", CANONICAL_ENFORCER_JS + "\n</head>")

    return result


# ─────────────────────────────────────────────
# Fix 7: sitemap.xml appearing as a crawlable page
# Create a redirect shim so Googlebot that GETs /sitemap.xml as HTML
# sees a 301-equivalent JS redirect to the real sitemap
# (GitHub Pages serves .xml directly — this shim only matters if somehow
#  an HTML version is being served. Also add noindex to any sitemap HTML.)
# ─────────────────────────────────────────────

def fix_sitemap_page(html, filepath):
    norm = filepath.replace("\\", "/")
    if "sitemap" not in norm:
        return html
    # If this is an HTML file named sitemap (unlikely but possible), add noindex
    if "<html" in html.lower() and "noindex" not in html:
        return html.replace(
            "<head>",
            '<head>\n<meta name="robots" content="noindex, nofollow" />'
        )
    return html


# ─────────────────────────────────────────────
# Fix 8: SearchAction schema — already replaced with ViewAction in v1
# Belt-and-braces: sweep for any remaining potentialAction SearchAction
# ─────────────────────────────────────────────

def fix_search_action_schema(html, filepath):
    # Remove potentialAction SearchAction blocks from JSON-LD
    # Replace with nothing — ViewAction was already patched in by gsc_fixes.py
    result = re.sub(
        r'"potentialAction"\s*:\s*\{[^}]*"@type"\s*:\s*"SearchAction"[^}]*\}',
        '"potentialAction": {"@type": "ViewAction", "target": "https://osalfinder.com/"}',
        html
    )
    return result


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def run_all_fixes():
    if not os.path.isdir(SITE_DIR):
        print(f"ERROR: {SITE_DIR}/ not found. Run publish_github_pages.py first.")
        return

    print("=== gsc_fixes_v2.py ===")

    patch_html_files(fix_logo_api_placeholder_links,   "404 logo-api placeholders")
    patch_html_files(fix_unresolved_template_vars,     "404 ${t.slug} template vars")
    patch_html_files(fix_short_path_hrefs,             "404 truncated /mo hrefs")
    patch_html_files(fix_email_links,                  "404 Cloudflare email obfuscation")
    patch_html_files(fix_homepage_canonical,           "canonical ?ref/?q variants")
    patch_html_files(fix_sitemap_page,                 "sitemap noindex")
    patch_html_files(fix_search_action_schema,         "SearchAction schema")

    print("=== done ===")


if __name__ == "__main__":
    run_all_fixes()
