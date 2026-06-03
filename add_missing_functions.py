"""
add_missing_functions.py
Adds fix_domain_references() and inject_canonical_redirect() to
publish_github_pages.py so the gsc_fixes.py calls don't fail.
Run from repo root: python add_missing_functions.py
"""
import sys
from pathlib import Path

TARGET   = Path("scripts/publish_github_pages.py")
SENTINEL = "# DOMAIN_FIX_FUNCTIONS_ADDED"

FUNCTIONS = '''
# DOMAIN_FIX_FUNCTIONS_ADDED
import re as _re

_REDIRECT_SNIPPET = (
    '<script>'
    '/* OSALFinder: redirect github.io mirror to canonical domain */'
    '(function(){{'
    'if(location.hostname.indexOf("github.io")!==-1){{'
    'var c=document.querySelector("link[rel=\\'canonical\\']");'
    'if(c&&c.href&&c.href.indexOf("osalfinder.com")!==-1)'
    '{{location.replace(c.href);}}'
    '}}'
    '}})();'
    '</script>'
)
_REDIRECT_SENTINEL = 'OSALFinder: redirect github.io mirror'


def inject_canonical_redirect(site_dir: str) -> None:
    """Inject JS redirect into every HTML page so github.io serves redirect to osalfinder.com."""
    from pathlib import Path as _Path
    injected = skipped = 0
    for html_file in _Path(site_dir).rglob('*.html'):
        try:
            content = html_file.read_text(encoding='utf-8', errors='ignore')
            if _REDIRECT_SENTINEL in content:
                skipped += 1
                continue
            if '<head>' in content:
                content = content.replace('<head>', '<head>' + _REDIRECT_SNIPPET, 1)
                html_file.write_text(content, encoding='utf-8')
                injected += 1
        except Exception as e:
            logger.warning(f"   redirect inject skipped {html_file.name}: {e}")
    logger.info(f"   🔀 Canonical redirect: injected {injected} pages, {skipped} already done")


def fix_domain_references(site_dir: str) -> None:
    """Replace any residual aiopentec.github.io references with osalfinder.com."""
    from pathlib import Path as _Path
    OLD_HTTPS = 'https://aiopentec.github.io/opensource-alternative-finder'
    OLD_HTTP  = 'http://aiopentec.github.io/opensource-alternative-finder'
    NEW_HTTPS = 'https://osalfinder.com'
    fixed_files = fixed_refs = 0
    for html_file in _Path(site_dir).rglob('*.html'):
        try:
            content = html_file.read_text(encoding='utf-8', errors='ignore')
            original = content
            content = content.replace(OLD_HTTPS, NEW_HTTPS)
            content = content.replace(OLD_HTTP,  NEW_HTTPS)
            if content != original:
                count = original.count(OLD_HTTPS) + original.count(OLD_HTTP)
                html_file.write_text(content, encoding='utf-8')
                fixed_files += 1
                fixed_refs  += count
        except Exception as e:
            logger.warning(f"   domain fix skipped {html_file.name}: {e}")
    sitemap = _Path(site_dir) / 'sitemap.xml'
    if sitemap.exists():
        c = sitemap.read_text(encoding='utf-8')
        o = c
        c = c.replace(OLD_HTTPS, NEW_HTTPS).replace(OLD_HTTP, NEW_HTTPS)
        if c != o:
            sitemap.write_text(c, encoding='utf-8')
            logger.info("   🗺️  Fixed github.io refs in sitemap.xml")
    if fixed_refs:
        logger.info(f"   🔧 Domain fix: {fixed_refs} refs across {fixed_files} files")
    else:
        logger.info("   ✅ Domain check: no github.io refs found")

'''


def patch():
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found. Run from repo root.")
        sys.exit(1)

    content = TARGET.read_text(encoding="utf-8")

    if SENTINEL in content:
        print("Already patched. No changes made.")
        sys.exit(0)

    # Insert the functions before build_site()
    if 'def build_site(' not in content:
        print("ERROR: Could not find def build_site() in publish_github_pages.py")
        sys.exit(1)

    content = content.replace('def build_site(', FUNCTIONS + 'def build_site(', 1)
    TARGET.write_text(content, encoding="utf-8")
    print("Done — fix_domain_references() and inject_canonical_redirect() added.")
    print("Trigger the pipeline in publish mode.")


if __name__ == "__main__":
    patch()
