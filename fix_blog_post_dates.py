#!/usr/bin/env python3
"""
fix_blog_post_dates.py
Every blog post's schema.org datePublished AND dateModified are currently
both stamped with today's date on every single pipeline run (build_blog(),
line ~3274), even though the 8 posts are static files in blog_content/
that the pipeline never edits. This is worse than the comparison-page
dateModified bug fixed earlier: it's not just claiming stale content is
fresh, it actively misreports when each post first went live, every day,
forever.

This patch adds real per-post date tracking:
  - A content hash is computed from each post's actual markdown file.
  - A persisted state file (data/cache/blog_state.json) stores each
    slug's first-seen date (datePublished) and the date its content hash
    last changed (dateModified).
  - datePublished is set once, the first time a slug is seen, and never
    changes again.
  - dateModified only advances if the post's actual file content changed
    since the last run.
  - data/cache/ is already committed back to the repo by the existing
    "Cache comparison data to repo" step in pipeline.yml (git add
    data/cache/), so blog_state.json rides along automatically — no
    workflow changes needed.

USAGE:
    Save this file in the ROOT of your opensource-alternative-finder repo,
    then run:

        python3 fix_blog_post_dates.py

Safe to re-run — skips if already applied.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET = "scripts/publish_github_pages.py"

MARKER = "blog_state"

# ── Edit 1: add hashlib import ───────────────────────────────────────────────
IMPORT_OLD = "import json, logging, os, re"
IMPORT_NEW = "import hashlib, json, logging, os, re"

# ── Edit 2: load blog state + helper, right after the `today`/`year` setup ──
LOAD_OLD = """def build_blog(site_dir: str, all_comparisons: List[Dict], updated: str):
    blog_dir  = Path(site_dir) / 'blog'
    blog_dir.mkdir(exist_ok=True)
    today     = datetime.utcnow().strftime('%Y-%m-%d')
    today_fmt = datetime.utcnow().strftime('%B %d, %Y')
    year      = datetime.utcnow().strftime('%Y')"""

LOAD_NEW = """def build_blog(site_dir: str, all_comparisons: List[Dict], updated: str):
    blog_dir  = Path(site_dir) / 'blog'
    blog_dir.mkdir(exist_ok=True)
    today     = datetime.utcnow().strftime('%Y-%m-%d')
    today_fmt = datetime.utcnow().strftime('%B %d, %Y')
    year      = datetime.utcnow().strftime('%Y')

    # ── Per-post publish/modified date tracking ──────────────────────────
    # datePublished and dateModified should reflect when a post's content
    # actually first appeared / last changed, not today's date on every
    # rebuild. State persists in data/cache/, which the pipeline already
    # commits back to the repo.
    blog_state_path = Path('data/cache/blog_state.json')
    if blog_state_path.exists():
        with open(blog_state_path) as f:
            blog_state = json.load(f)
    else:
        blog_state = {}

    def get_blog_dates(slug: str, content_file: Path):
        if content_file.exists():
            content_hash = hashlib.sha256(content_file.read_bytes()).hexdigest()[:16]
        else:
            content_hash = 'no-file'
        prev = blog_state.get(slug)
        if prev:
            published = prev.get('published', today)
            modified = today if prev.get('hash') != content_hash else prev.get('modified', published)
        else:
            published = today
            modified = today
        blog_state[slug] = {'hash': content_hash, 'published': published, 'modified': modified}
        return published, modified"""

# ── Edit 3: compute real dates per post, right where content_file is resolved ──
CALLSITE_OLD = """        repo_root = Path.cwd()
        content_file = repo_root / 'blog_content' / f"{tmpl['slug']}.md"
        body_sections = ''"""

CALLSITE_NEW = """        repo_root = Path.cwd()
        content_file = repo_root / 'blog_content' / f"{tmpl['slug']}.md"
        post_published, post_modified = get_blog_dates(tmpl['slug'], content_file)
        body_sections = ''"""

# ── Edit 4: use the real dates in the JSON-LD instead of `today` ────────────
JSONLD_OLD = '\"dateModified\":\"{today}\",\"datePublished\":\"{today}\",'
JSONLD_NEW = '\"dateModified\":\"{post_modified}\",\"datePublished\":\"{post_published}\",'

# ── Edit 5: persist state after the post loop finishes ───────────────────────
SAVE_ANCHOR_OLD = """    comp_by_slug = {c.get('slug',''): c for c in all_comparisons}
    posts_built  = []

    for tmpl in POST_TEMPLATES:"""

SAVE_ANCHOR_NEW = """    comp_by_slug = {c.get('slug',''): c for c in all_comparisons}
    posts_built  = []

    def _save_blog_state():
        blog_state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(blog_state_path, 'w') as f:
            json.dump(blog_state, f, indent=2)

    for tmpl in POST_TEMPLATES:"""


def main():
    path = os.path.join(ROOT, TARGET)
    if not os.path.exists(path):
        print(f"ERROR: {TARGET} not found. Run this from the repo root.")
        sys.exit(1)

    with open(path) as f:
        src = f.read()

    if MARKER in src:
        print(f"SKIP: {TARGET} already patched.")
        return

    if src.count(JSONLD_OLD) != 1:
        print(f"ERROR: expected exactly one occurrence of the blog JSON-LD date block, "
              f"found {src.count(JSONLD_OLD)}. Your file may differ from what this patch "
              f"expects — no changes written. Check manually.")
        sys.exit(1)

    for label, old, new in [
        ("hashlib import", IMPORT_OLD, IMPORT_NEW),
        ("load blog state + helper function", LOAD_OLD, LOAD_NEW),
        ("compute real dates per post", CALLSITE_OLD, CALLSITE_NEW),
        ("use real dates in JSON-LD", JSONLD_OLD, JSONLD_NEW),
        ("prepare state-save helper before post loop", SAVE_ANCHOR_OLD, SAVE_ANCHOR_NEW),
    ]:
        if old not in src:
            print(f"ERROR: could not find the expected '{label}' block. Your file may "
                  f"differ from what this patch expects — no changes written. Check manually.")
            sys.exit(1)
        src = src.replace(old, new)
        print(f"Patched: {label}")

    # Call the save helper once, right after the post loop — anchor on the
    # `posts_built` list being used after the loop completes.
    END_LOOP_OLD = "    return posts_built"
    END_LOOP_NEW = "    _save_blog_state()\n    return posts_built"
    if END_LOOP_OLD not in src:
        print("ERROR: could not find the end of build_blog() to persist state. "
              "No changes written. Check manually.")
        sys.exit(1)
    src = src.replace(END_LOOP_OLD, END_LOOP_NEW, 1)
    print("Patched: persist state at end of build_blog()")

    with open(path, "w") as f:
        f.write(src)

    print(f"\nDone. {TARGET} now tracks real per-post publish/modified dates in "
          f"data/cache/blog_state.json.")
    print("First run after this patch sets every post's published/modified date to "
          "today (nothing to compare against yet) — dates will only diverge from there "
          "once a post's actual file content changes on a later run.")


if __name__ == "__main__":
    main()
