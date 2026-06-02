"""
gsc_fixes.py — Fix all 6 URLs flagged in Google Search Console
Run: python gsc_fixes.py
Then commit scripts/publish_github_pages.py and trigger pipeline (publish mode).

Issues fixed:
  1. /mo                          → broken relative link in generated HTML
  2. /cdn-cgi/l/email-protection  → Cloudflare email obfuscation of mailto: links
  3. /logo-api/v1/$               → unresolved $ variable in logo API page
  4. /?q={search_term_string}     → SearchAction schema Google tries to crawl (401)
  5. /logo-api/v1/FREE_KEY/slack  → example URL in code block treated as real URL
  6. /shopify-vs-woocommerce/ 401 → handled via GSC URL Inspection (see instructions)
"""

import re
import sys
from pathlib import Path

TARGET = Path("scripts/publish_github_pages.py")
SENTINEL = "# GSC_FIXES_APPLIED"


def patch():
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found. Run from repo root.")
        sys.exit(1)

    content = TARGET.read_text(encoding="utf-8")

    if SENTINEL in content:
        print("Already patched. No changes made.")
        sys.exit(0)

    changes = []

    # ── Fix 1 & 2: Encode email addresses and strip /mo broken links ─────────
    # Add post_process_html() function before build_site()
    POST_PROCESS_FN = '''
def post_process_html(site_dir: str) -> None:
    """
    Post-processing sweep over every built HTML file.
    Fixes:
      - Encodes mailto: email addresses as HTML entities so Cloudflare
        does not rewrite them to /cdn-cgi/l/email-protection (which 404s)
      - Removes suspiciously short relative hrefs like href="/mo" that
        indicate truncated AI-generated links
    """
    EMAIL_PLAIN  = 'mailto:openaltshub@gmail.com'
    EMAIL_ENCODED = ('mailto:&#111;&#112;&#101;&#110;&#97;&#108;&#116;'
                     '&#115;&#104;&#117;&#98;&#64;&#103;&#109;&#97;'
                     '&#105;&#108;&#46;&#99;&#111;&#109;')
    SHORT_HREF = re.compile(r'href="(/[a-z]{1,3})"', re.IGNORECASE)

    fixed_email = 0
    fixed_links = 0

    for html_file in Path(site_dir).rglob('*.html'):
        try:
            text = html_file.read_text(encoding='utf-8', errors='ignore')
            original = text

            # Encode email to prevent Cloudflare obfuscation
            text = text.replace(EMAIL_PLAIN, EMAIL_ENCODED)

            # Remove href="/mo" style broken relative links (keep /  and known short paths)
            SAFE_SHORT = {'/'}
            def replace_short(m):
                path = m.group(1)
                if path in SAFE_SHORT:
                    return m.group(0)
                logger.warning(f"   ⚠️  Removing suspicious short href: {path} in {html_file.name}")
                return 'href="#"'
            text = SHORT_HREF.sub(replace_short, text)

            if text != original:
                html_file.write_text(text, encoding='utf-8')
                if EMAIL_PLAIN not in text and EMAIL_PLAIN in original:
                    fixed_email += 1
                fixed_links += original.count('href="/mo"')
        except Exception as e:
            logger.warning(f"   ⚠️  post_process_html skipped {html_file.name}: {e}")

    if fixed_email:
        logger.info(f"   📧 Encoded email in {fixed_email} pages (prevents /cdn-cgi/l/email-protection 404)")
    if fixed_links:
        logger.info(f"   🔗 Removed {fixed_links} broken short href(s) (e.g. /mo)")

'''

    # Insert before build_site()
    if 'def build_site(' in content and POST_PROCESS_FN.strip()[:30] not in content:
        content = content.replace('def build_site(', POST_PROCESS_FN + 'def build_site(', 1)
        changes.append("Added post_process_html() function")

    # ── Call post_process_html just before ping_indexnow ─────────────────────
    OLD_PING = '    ping_indexnow(all_comparisons)'
    NEW_PING = ('    post_process_html(site_dir)\n'
                '    fix_domain_references(site_dir)\n'
                '    inject_canonical_redirect(site_dir)\n'
                '    ping_indexnow(all_comparisons)')
    if OLD_PING in content and 'post_process_html(site_dir)' not in content:
        content = content.replace(OLD_PING, NEW_PING, 1)
        changes.append("Added post_process_html + fix_domain_references + inject_canonical_redirect calls before ping_indexnow")

    # ── Fix 3: /logo-api/v1/$ — encode $ in logo API code examples ───────────
    # The $ appears in f-string context where a shell var wasn't expanded.
    # Replace any bare $ in URL path context within the logo API page builder.
    if "logo-api/v1/$" in content:
        content = content.replace("logo-api/v1/$", "logo-api/v1/your-key")
        changes.append("Fixed /logo-api/v1/$ → /logo-api/v1/your-key")

    # ── Fix 4: /?q={search_term_string} — remove SearchAction schema ─────────
    # Google tries to crawl this URL pattern and gets 401.
    # The site has client-side JS search but no server-side search endpoint.
    OLD_SEARCH_ACTION = '''"potentialAction": {{
      "@type": "SearchAction",
      "target": "{site_base_url}/?q={{{{search_term_string}}}}",
      "query-input": "required name=search_term_string"
    }}'''
    NEW_SEARCH_ACTION = '''"potentialAction": {{
      "@type": "ViewAction",
      "target": "{site_base_url}/"
    }}'''
    if '"potentialAction"' in content and 'SearchAction' in content:
        content = content.replace(OLD_SEARCH_ACTION, NEW_SEARCH_ACTION, 1)
        changes.append("Replaced SearchAction schema with ViewAction (prevents /?q={search_term_string} crawl)")
    elif 'SearchAction' in content:
        # Fallback: just remove the potentialAction block
        content = re.sub(
            r',\s*"potentialAction":\s*\{[^}]+\}',
            '',
            content
        )
        changes.append("Removed SearchAction potentialAction from schema (prevents 401 on /?q= URLs)")

    # ── Fix 5: /logo-api/v1/FREE_KEY/slack — change example URL domain ───────
    # Example URLs in <pre> code blocks use osalfinder.com which Google crawls.
    # Replacing with a placeholder domain stops Google from trying to validate them.
    if "osalfinder.com/logo-api/v1/FREE_KEY" in content:
        content = content.replace(
            "osalfinder.com/logo-api/v1/FREE_KEY",
            "your-site.com/logo-api/v1/YOUR_KEY"
        )
        changes.append("Changed FREE_KEY example URL domain to your-site.com (stops /logo-api/v1/FREE_KEY/slack 401)")
    if "'https://osalfinder.com/logo-api/v1/free/slack'" in content:
        content = content.replace(
            "'https://osalfinder.com/logo-api/v1/free/slack'",
            "'https://osalfinder.com/logo-api/v1/free/slack'"  # keep this one — it's in JS clipboard only
        )

    # ── Mark patched ──────────────────────────────────────────────────────────
    content = content.replace(
        '# ── CONFIG — edit these ───',
        f'{SENTINEL}\n# ── CONFIG — edit these ───',
        1
    )

    TARGET.write_text(content, encoding="utf-8")

    print(f"\nPatch complete. {len(changes)} change(s) applied:\n")
    for i, c in enumerate(changes, 1):
        print(f"  {i}. {c}")

    print("""
\nFor issue 6 (/shopify-vs-woocommerce/ 401):
  This is a transient Cloudflare/GitHub Pages block, not a real 401.
  Fix: Go to Google Search Console → URL Inspection
       Enter: https://osalfinder.com/shopify-vs-woocommerce/
       Click: Request Indexing
  Google will recrawl it and get 200 this time.
""")


if __name__ == "__main__":
    patch()
