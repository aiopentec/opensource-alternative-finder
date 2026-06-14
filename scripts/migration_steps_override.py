"""
migration_steps_override.py

Detailed, real migration steps for the top 5 highest-traffic migration pairs.
These replace the generic 4-6 step fallback in extract_migration_steps()
inside scripts/publish_github_pages.py.

USAGE:
In publish_github_pages.py, inside build_migration_page(), find this block:

    steps = extract_migration_steps(comp.get('comparison_markdown', ''))
    if not steps:
        steps = [
            f"Export your data from {prop_name} using their built-in export tool (Settings → Export)",
            ...
        ]

Replace it with:

    steps = extract_migration_steps(comp.get('comparison_markdown', ''))
    override_key = f"{prop_key}-to-{oss_key}"
    if override_key in MIGRATION_STEPS_OVERRIDE:
        steps = MIGRATION_STEPS_OVERRIDE[override_key]
    elif not steps:
        steps = [ ... existing generic fallback ... ]

And add this import near the top of publish_github_pages.py:

    from migration_steps_override import MIGRATION_STEPS_OVERRIDE

(Place migration_steps_override.py in scripts/ alongside publish_github_pages.py)
"""

MIGRATION_STEPS_OVERRIDE = {

    # ── Figma → Penpot ──────────────────────────────────────────────────
    "figma-to-penpot": [
        "Install the official Penpot Exporter plugin from the Figma Community — search \"Penpot Exporter\" in Figma's plugin browser and add it to your account",
        "Open the Figma file you want to migrate, run the plugin from the Plugins menu, and select \"Export\". The plugin generates a .penpot file containing your pages, frames, and layer structure",
        "In Penpot, go to your Projects dashboard, click the three-dot menu, and select \"Import Penpot files\". Choose the exported file — Penpot will create a new project matching your Figma file's structure",
        "Check text layers first: fonts that aren't available in Penpot will show a warning. Either upload the font file or substitute a close match before continuing",
        "Review auto-layout: simple flex-based layouts transfer cleanly, but complex nested auto-layout frames often need manual adjustment to padding and alignment after import",
        "Components import as plain groups, not reusable components. Right-click each one and select \"Create Component\" to restore the component/instance relationship",
        "Color variables do not transfer — this is the plugin's main known limitation. Rebuild your color palette as Penpot design tokens (Assets panel → Tokens) using your original Figma styles as reference",
        "For design systems specifically: migrate one small, low-risk project first to learn the quirks before attempting your full component library. Archived or rarely-used files can stay in Figma's free viewer rather than being migrated",
    ],

    # ── Slack → Mattermost ──────────────────────────────────────────────
    "slack-to-mattermost": [
        "Export your Slack workspace data: Workspace Settings → Import/Export Data → Export. Note that free and Pro plans only export public channel history — private channels and DMs require a Business+ or Enterprise export",
        "Download and install mmetl (the Mattermost ETL tool) from Mattermost's GitHub releases — it's the official tool for converting Slack exports into Mattermost's import format",
        "Run `mmetl check` on your Slack export zip first to validate the file structure and catch problems before conversion",
        "Convert the export: `mmetl convert slack_export.zip mattermost_import.jsonl` — this processes messages, users, channels, and timestamps into a single JSONL file",
        "Before importing, create the destination team in Mattermost manually, and enable \"Allow any user with an account on this server to join this team\" in the team settings — the import will fail without this",
        "Check for email mismatches between Slack and Mattermost accounts before importing. Mismatched emails cause messages to be attributed to placeholder accounts instead of the correct user",
        "Upload and process the import using mmctl: `mmctl import upload mattermost_import.jsonl` followed by `mmctl import process <upload-id>`. The import is idempotent — re-running it won't create duplicate posts",
        "If the import fails on file size, increase Mattermost's MaxFileSize setting in config.json before retrying. For large imports, use the `--workers 4` flag with mmetl to speed up conversion",
    ],

    # ── Notion → AppFlowy ─────────────────────────────────────────────
    "notion-to-appflowy": [
        "In Notion, go to Settings & Members → Settings → Export all workspace content. Choose \"Markdown & CSV\" as the format — this generates a zip with all pages as Markdown files and databases as CSV",
        "In the AppFlowy desktop app, use the built-in Notion importer (File → Import → Notion) and select the exported zip. AppFlowy reconstructs your page hierarchy automatically",
        "Run a test import first: pick 5-10 of your most important documents, import just those, and verify formatting, headings, and links came through correctly before importing everything",
        "Simple databases with standard properties (text, number, select, date) import cleanly as AppFlowy grid views. Complex databases with linked relations or rollup formulas will need to be rebuilt manually",
        "Re-upload embedded files: PDFs, images, and videos embedded in Notion pages don't transfer automatically and need to be re-attached in AppFlowy after import",
        "For pages using Notion-specific blocks (synced blocks, linked database views, toggle lists with complex nesting), expect to manually reformat — these don't have direct AppFlowy equivalents",
        "Once imported, set up AppFlowy Cloud if you need team collaboration — self-host via Docker Compose for free, or use the hosted Pro tier for managed sync across your team",
    ],

    # ── Jira → Plane ──────────────────────────────────────────────────
    "jira-to-plane": [
        "Before migrating, clean up your Jira backlog: archive issues older than 6 months, standardize labels, and remove unused custom fields. Migrating Jira's accumulated mess into Plane just recreates the same problems",
        "Export your Jira project as CSV: Project Settings → Issues → Export → CSV (current fields). For multiple projects, export each one separately",
        "Set up Plane first — either the cloud free tier or self-hosted via Docker Compose (plane.so/self-host). A 4GB RAM server handles teams up to 50 comfortably",
        "In Plane, create matching workspaces/projects for each Jira project before importing, so issues land in the right place",
        "Use Plane's CSV importer (Settings → Imports → Jira) to bring in issues. Map Jira's status names to Plane's states (Backlog, Todo, In Progress, Done, Cancelled) during the mapping step",
        "Jira epics map to Plane modules, and Jira sprints map to Plane cycles — but these don't auto-import from CSV. Recreate your current sprint structure manually in Plane after the issue import",
        "Custom workflow automations (Jira Automation rules) don't transfer. Audit which automations your team actually relies on and rebuild the critical ones using Plane's automation features or webhooks",
        "Never migrate mid-sprint. Finish the current Jira sprint, do the migration during a planned break between sprints, and start the next cycle fresh in Plane",
    ],

    # ── GitHub → Gitea ───────────────────────────────────────────────
    "github-to-gitea": [
        "Set up your Gitea or Forgejo instance first via Docker Compose (a 1-2GB RAM VPS is sufficient for most teams) — complete the setup wizard and create your organization structure before migrating repos",
        "Generate a GitHub personal access token with repo read access — Gitea's migration wizard needs this to pull your repositories",
        "Use Gitea's built-in migration tool (+ → New Migration → GitHub) for each repository. This pulls commit history, issues, pull requests, labels, milestones, and releases in one operation",
        "For repositories you want to keep in sync during a transition period, use Gitea's repository mirroring feature instead of a one-time migration — commits to GitHub will automatically sync to Gitea",
        "Audit your GitHub Actions workflows: most standard actions (checkout, setup-node, setup-python) have Forgejo/Gitea Actions-compatible equivalents and will run with little to no modification",
        "Marketplace actions with no Forgejo equivalent need to be rewritten as custom scripts or replaced with self-hosted alternatives — identify these before cutover, not after",
        "GitHub Packages don't migrate automatically — re-publish your package artifacts to Gitea's built-in package registry (supports npm, Docker, PyPI, Maven, and more)",
        "Migrate one repository at a time, verify CI/CD works end-to-end on Gitea, then move to the next. Don't attempt an organization-wide cutover in a single day",
    ],
}
