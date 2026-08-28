#!/usr/bin/env python3
"""
fix_about_page_disclosure.py
The /about/ page currently states, in two places, that "No human reviews
each page before it goes live... not manual editorial oversight" with no
mention of any automated check either. That's honest, but it reads as a
direct admission of exactly the pattern AdSense's "Low value content" /
scaled-content-abuse review is designed to catch — mass-produced pages
with zero quality control of any kind.

This patch requires the pipeline.yml change (Audit Migrate Page Content
step) to already be applied — it makes the About page's disclosure
accurately describe that real gate, rather than just softening the
wording without anything backing it up. Still fully honest: still says
no human reviews each page individually, still says a check on length
isn't a check on accuracy — just no longer implies zero quality control
exists at all.

USAGE:
    Save this file in the ROOT of your opensource-alternative-finder repo,
    then run:

        python3 fix_about_page_disclosure.py

Safe to re-run — skips if already applied.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET = "scripts/publish_github_pages.py"

MARKER = "content-quality audit measures"

OLD_1 = """          <strong>The whole cycle repeats every 24 hours</strong>
          <span>No human reviews each page before it goes live. The quality control is in the prompt design, the structured data inputs, and the fallback logic — not manual editorial oversight. If something is wrong, it gets corrected when reported.</span>"""

NEW_1 = """          <strong>The whole cycle repeats every 24 hours</strong>
          <span>No human reviews each page individually before it goes live, but every page is checked automatically: a content-quality audit measures unique word count against the same threshold AdSense uses to define "thin content," and the pipeline refuses to deploy if any page falls short. Beyond that, quality control is in the prompt design, the structured data inputs, and the fallback logic. If something is still wrong, it gets corrected when reported.</span>"""

OLD_2 = """      <li>No human reviews each page before it publishes. Errors can and do appear. When they are reported, they are corrected within 24 hours.</li>"""

NEW_2 = """      <li>No human reviews each page individually before it publishes, though an automated content-quality check runs before every deploy and blocks publishing if a page falls below the minimum-content threshold. That check verifies length, not accuracy — errors of substance can still appear. When reported, they are corrected within 24 hours.</li>"""


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

    for label, old, new in [
        ("'whole cycle repeats' disclosure", OLD_1, NEW_1),
        ("'What This Site Does Not Do' list item", OLD_2, NEW_2),
    ]:
        if old not in src:
            print(f"ERROR: could not find the expected '{label}' block. Your file may "
                  f"differ from what this patch expects — no changes written. Check manually.")
            sys.exit(1)
        src = src.replace(old, new)
        print(f"Patched: {label}")

    with open(path, "w") as f:
        f.write(src)

    print(f"\nDone. {TARGET} About page now accurately describes the automated "
          f"content-quality gate instead of implying zero quality control.")
    print("Make sure the pipeline.yml 'Audit Migrate Page Content' step is applied "
          "too — this wording only stays honest if that gate is actually real.")


if __name__ == "__main__":
    main()
