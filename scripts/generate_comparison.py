#!/usr/bin/env python3
"""
generate_comparison.py
Generates AI comparison pages using free APIs:
  Primary:  Groq (llama-3.3-70b-versatile) — free, fast
  Fallback: Google Gemini Flash             — free, reliable
  Last:     Template engine                 — always works, no API needed

Usage: python scripts/generate_comparison.py --index 1
"""

import argparse, json, logging, os, sys, time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import requests

sys.path.insert(0, str(Path(__file__).parent))
from utils_resilience import CircuitBreaker, DeadLetterQueue, send_slack_alert

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# TOOL DATABASE  (edit this to add more tools)
# ──────────────────────────────────────────────────────────────
TOOLS = {
    'slack':           {'name': 'Slack',           'category': 'communication',      'pricing': '$7.25–$15/user/month',    'license': 'Proprietary',               'website': 'https://slack.com',           'description': 'Team messaging platform with channels, DMs, and thousands of integrations. The industry standard for workplace chat.',           'founded': '2013', 'company': 'Salesforce'},
    'element':         {'name': 'Element',          'category': 'communication',      'pricing': 'Free (self-hosted)',       'license': 'Apache 2.0',                'website': 'https://element.io',          'description': 'Decentralized, end-to-end encrypted messaging built on the open Matrix protocol. Full data ownership.',                         'github': 'element-hq/element-web',  'stars_approx': '11k'},
    'mattermost':      {'name': 'Mattermost',       'category': 'communication',      'pricing': 'Free (self-hosted)',       'license': 'MIT / AGPL',                'website': 'https://mattermost.com',      'description': 'Open-source workplace messaging built for developers and DevOps teams. Highly extensible.',                                     'github': 'mattermost/mattermost',   'stars_approx': '30k'},
    'notion':          {'name': 'Notion',           'category': 'productivity',       'pricing': '$8–$20/user/month',       'license': 'Proprietary',               'website': 'https://notion.so',           'description': 'All-in-one workspace combining notes, databases, wikis, and project management. Widely used for personal and team knowledge.',   'founded': '2016', 'company': 'Notion Labs'},
    'appflowy':        {'name': 'AppFlowy',         'category': 'productivity',       'pricing': 'Free',                    'license': 'GPL 3.0',                   'website': 'https://appflowy.io',         'description': 'Open-source Notion alternative with local-first storage, offline support, and strong privacy guarantees.',                     'github': 'AppFlowy-IO/AppFlowy',    'stars_approx': '59k'},
    'obsidian':        {'name': 'Obsidian',         'category': 'productivity',       'pricing': 'Free (local use)',         'license': 'Proprietary (free personal)','website': 'https://obsidian.md',        'description': 'Local-first knowledge base using plain Markdown files. Extremely fast, highly extensible with 1,000+ community plugins.',       'founded': '2020', 'company': 'Dynalist Inc'},
    'logseq':          {'name': 'Logseq',           'category': 'productivity',       'pricing': 'Free',                    'license': 'AGPL 3.0',                  'website': 'https://logseq.com',          'description': 'Open-source outliner and knowledge management tool using plain text files. Privacy-first, works fully offline.',                'github': 'logseq/logseq',           'stars_approx': '33k'},
    'github':          {'name': 'GitHub',           'category': 'developer-tools',    'pricing': 'Free / $7–$21/user',      'license': 'Proprietary',               'website': 'https://github.com',          'description': 'The world\'s largest code hosting and collaboration platform. Owned by Microsoft since 2018.',                                   'founded': '2008', 'company': 'Microsoft'},
    'gitlab':          {'name': 'GitLab',           'category': 'developer-tools',    'pricing': 'Free (self-hosted)',       'license': 'MIT (CE)',                  'website': 'https://gitlab.com',          'description': 'Complete DevOps platform with built-in CI/CD, issue tracking, container registry, and more. Can be fully self-hosted.',        'github': 'gitlabhq/gitlabhq',       'stars_approx': '24k'},
    'gitea':           {'name': 'Gitea',            'category': 'developer-tools',    'pricing': 'Free (self-hosted)',       'license': 'MIT',                       'website': 'https://gitea.io',            'description': 'Lightweight, fast self-hosted Git service. Very low memory footprint, easy to install on a Raspberry Pi.',                     'github': 'go-gitea/gitea',          'stars_approx': '44k'},
    'figma':           {'name': 'Figma',            'category': 'design',             'pricing': '$12–$75/user/month',      'license': 'Proprietary',               'website': 'https://figma.com',           'description': 'Browser-based collaborative design and prototyping tool. The dominant tool for UI/UX design teams.',                            'founded': '2012', 'company': 'Adobe'},
    'penpot':          {'name': 'Penpot',           'category': 'design',             'pricing': 'Free',                    'license': 'MPL 2.0',                   'website': 'https://penpot.app',          'description': 'Open-source design and prototyping platform that works in the browser. Uses open SVG-based format for all files.',              'github': 'penpot/penpot',           'stars_approx': '33k'},
    'jira':            {'name': 'Jira',             'category': 'project-management', 'pricing': '$7.75–$14.50/user/month', 'license': 'Proprietary',               'website': 'https://atlassian.com/jira',  'description': 'Industry-leading issue and project tracking software for agile teams. Part of the Atlassian ecosystem.',                       'founded': '2002', 'company': 'Atlassian'},
    'plane':           {'name': 'Plane',            'category': 'project-management', 'pricing': 'Free (self-hosted)',       'license': 'Apache 2.0',                'website': 'https://plane.so',            'description': 'Open-source project management tool designed as a Jira alternative with a modern, fast UI.',                                   'github': 'makeplane/plane',         'stars_approx': '31k'},
    'linear':          {'name': 'Linear',           'category': 'project-management', 'pricing': 'Free / $8/user/month',    'license': 'Proprietary',               'website': 'https://linear.app',          'description': 'Streamlined issue tracker known for speed and keyboard-first design. Very popular with software startups.',                    'founded': '2019', 'company': 'Linear'},
    'trello':          {'name': 'Trello',           'category': 'project-management', 'pricing': 'Free / $5+/user/month',   'license': 'Proprietary',               'website': 'https://trello.com',          'description': 'Visual kanban board tool with cards, lists, and boards. Simple and beginner-friendly. Owned by Atlassian.',                    'founded': '2011', 'company': 'Atlassian'},
    'wekan':           {'name': 'WeKan',            'category': 'project-management', 'pricing': 'Free (self-hosted)',       'license': 'MIT',                       'website': 'https://wekan.github.io',     'description': 'Open-source kanban board that can be self-hosted. Supports standard kanban features with no vendor lock-in.',                  'github': 'wekan/wekan',             'stars_approx': '20k'},
    'dropbox':         {'name': 'Dropbox',          'category': 'file-storage',       'pricing': '$9.99–$16.58/user/month', 'license': 'Proprietary',               'website': 'https://dropbox.com',         'description': 'Pioneer cloud file storage and sync service. Simple to use, integrates with many tools.',                                      'founded': '2007', 'company': 'Dropbox Inc'},
    'nextcloud':       {'name': 'Nextcloud',        'category': 'file-storage',       'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://nextcloud.com',       'description': 'The most popular self-hosted cloud storage platform. Includes file sync, calendar, contacts, video calls, and 400+ apps.',    'github': 'nextcloud/server',        'stars_approx': '27k'},
    'zoom':            {'name': 'Zoom',             'category': 'video-conferencing', 'pricing': 'Free / $13.33+/user/month','license': 'Proprietary',              'website': 'https://zoom.us',             'description': 'Dominant video conferencing platform since 2020. Known for reliability and ease of use.',                                     'founded': '2011', 'company': 'Zoom Video Communications'},
    'jitsi':           {'name': 'Jitsi Meet',       'category': 'video-conferencing', 'pricing': 'Free',                    'license': 'Apache 2.0',                'website': 'https://jitsi.org',           'description': 'Open-source video conferencing that works entirely in the browser. No account needed. Can be self-hosted.',                   'github': 'jitsi/jitsi-meet',        'stars_approx': '23k'},
    'discord':         {'name': 'Discord',          'category': 'communication',      'pricing': 'Free / $9.99/month',      'license': 'Proprietary',               'website': 'https://discord.com',         'description': 'Chat platform popular with gaming and developer communities. Supports voice, video, text, and screen sharing.',                'founded': '2015', 'company': 'Discord Inc'},
    'zulip':           {'name': 'Zulip',            'category': 'communication',      'pricing': 'Free (self-hosted)',       'license': 'Apache 2.0',                'website': 'https://zulip.com',           'description': 'Open-source team chat with a unique threaded model that keeps conversations organized even in busy teams.',                   'github': 'zulip/zulip',             'stars_approx': '21k'},
    'asana':           {'name': 'Asana',            'category': 'project-management', 'pricing': 'Free / $10.99+/user',     'license': 'Proprietary',               'website': 'https://asana.com',           'description': 'Work management platform for tracking tasks, projects, and team goals. Used by 150,000+ organizations.',                       'founded': '2008', 'company': 'Asana Inc'},
    'taiga':           {'name': 'Taiga',            'category': 'project-management', 'pricing': 'Free (self-hosted)',       'license': 'MPL 2.0',                   'website': 'https://taiga.io',            'description': 'Open-source agile project management tool supporting Scrum, Kanban, and Scrumban boards.',                                    'github': 'taigaio/taiga-back',      'stars_approx': '8k'},
    'microsoft-teams': {'name': 'Microsoft Teams',  'category': 'communication',      'pricing': 'Free / $6–$22/user/month','license': 'Proprietary',               'website': 'https://microsoft.com/teams', 'description': 'Microsoft\'s workplace chat and video conferencing platform, tightly integrated with Office 365 and the Microsoft ecosystem.',  'founded': '2017', 'company': 'Microsoft'},
    'google-workspace':{'name': 'Google Workspace', 'category': 'productivity',       'pricing': '$6–$18/user/month',       'license': 'Proprietary',               'website': 'https://workspace.google.com','description': 'Google\'s suite of cloud productivity tools including Gmail, Drive, Docs, Sheets, Meet, and Calendar.',                          'founded': '2006', 'company': 'Google'},
    'airtable':        {'name': 'Airtable',         'category': 'productivity',       'pricing': 'Free / $10–$20/user/month','license': 'Proprietary',              'website': 'https://airtable.com',        'description': 'Flexible spreadsheet-database hybrid for organizing anything. Popular for project tracking, CRM, and content calendars.',     'founded': '2012', 'company': 'Airtable Inc'},
    'nocodb':          {'name': 'NocoDB',           'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://nocodb.com',          'description': 'Open-source Airtable alternative that turns any database into a smart spreadsheet. Supports MySQL, Postgres, SQLite.',        'github': 'nocodb/nocodb',           'stars_approx': '45k'},
    'monday':          {'name': 'Monday.com',       'category': 'project-management', 'pricing': '$9–$19/user/month',       'license': 'Proprietary',               'website': 'https://monday.com',          'description': 'Visual work management platform used by 180,000+ organizations for project tracking, CRM, and workflow automation.',          'founded': '2012', 'company': 'monday.com Ltd'},
    'hubspot':         {'name': 'HubSpot',          'category': 'productivity',       'pricing': 'Free / $15–$800+/month',  'license': 'Proprietary',               'website': 'https://hubspot.com',         'description': 'All-in-one CRM, marketing, sales, and customer service platform. Used by 200,000+ businesses worldwide.',                     'founded': '2006', 'company': 'HubSpot Inc'},
    'suitecrm':        {'name': 'SuiteCRM',         'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://suitecrm.com',        'description': 'The world\'s most popular open-source CRM. A full-featured fork of SugarCRM with enterprise capabilities.',                   'github': 'salesagility/SuiteCRM',   'stars_approx': '4k'},
    'mailchimp':       {'name': 'Mailchimp',        'category': 'productivity',       'pricing': 'Free / $13–$350+/month',  'license': 'Proprietary',               'website': 'https://mailchimp.com',       'description': 'Leading email marketing platform with automation, landing pages, and analytics. Used by 11 million businesses.',              'founded': '2001', 'company': 'Intuit'},
    'listmonk':        {'name': 'Listmonk',         'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://listmonk.app',        'description': 'High-performance, self-hosted newsletter and mailing list manager. Handles millions of emails with a tiny footprint.',        'github': 'knadh/listmonk',          'stars_approx': '15k'},
    'wordpress-com':   {'name': 'WordPress.com',    'category': 'productivity',       'pricing': 'Free / $4–$45+/month',    'license': 'Proprietary',               'website': 'https://wordpress.com',       'description': 'Hosted blogging and website platform. Easy to use but limits customization compared to self-hosted WordPress.',               'founded': '2005', 'company': 'Automattic'},
    'ghost':           {'name': 'Ghost',            'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'MIT',                       'website': 'https://ghost.org',           'description': 'Open-source publishing platform built for professional bloggers and creators. Fast, clean, and membership-ready.',            'github': 'TryGhost/Ghost',          'stars_approx': '47k'},
}

# ──────────────────────────────────────────────────────────────
# COMPARISON PAIRS  (proprietary → open-source alternative)
# ──────────────────────────────────────────────────────────────
COMPARISON_PAIRS = [
    ('slack',            'element'),
    ('slack',            'mattermost'),
    ('slack',            'zulip'),
    ('discord',          'element'),
    ('notion',           'appflowy'),
    ('notion',           'obsidian'),
    ('notion',           'logseq'),
    ('github',           'gitlab'),
    ('github',           'gitea'),
    ('figma',            'penpot'),
    ('jira',             'plane'),
    ('trello',           'wekan'),
    ('dropbox',          'nextcloud'),
    ('zoom',             'jitsi'),
    ('linear',           'plane'),
    ('asana',            'taiga'),
    ('microsoft-teams',  'mattermost'),
    ('google-workspace', 'nextcloud'),
    ('airtable',         'nocodb'),
    ('monday',           'plane'),
    ('hubspot',          'suitecrm'),
    ('mailchimp',        'listmonk'),
    ('wordpress-com',    'ghost'),
]


# ──────────────────────────────────────────────────────────────
# PROMPT BUILDER
# ──────────────────────────────────────────────────────────────
def build_prompt(prop_key: str, oss_key: str) -> str:
    prop = TOOLS.get(prop_key, {})
    alt  = TOOLS.get(oss_key,  {})
    month = datetime.now().strftime('%B %Y')
    return f"""You are a technical writer. Generate a structured Markdown comparison page.

# {prop.get('name', prop_key)} vs {alt.get('name', oss_key)}

Write the following sections in Markdown. Be objective, factual, and concise.

## Overview
2-3 sentences: what both tools do and who benefits from this comparison.

## Key Differences
5 bullet points covering: cost, data ownership, setup complexity, scalability, and ecosystem.

## Pricing Comparison
| Aspect | {prop.get('name', prop_key)} | {alt.get('name', oss_key)} |
|--------|----------|---------|
| Base Cost | {prop.get('pricing', 'N/A')} | {alt.get('pricing', 'Free')} |
| License | {prop.get('license', 'Proprietary')} | {alt.get('license', 'Open Source')} |
| Self-hosting | Not available | Available |
| Per-user cost at 50 users | Calculate approximate | Calculate approximate |

## Pros and Cons
Bullet lists of pros and cons for each tool.

## When to Choose Each
Short paragraph for each tool describing the ideal user profile.

## Migration Path
2-3 practical steps someone would take to migrate from {prop.get('name', prop_key)} to {alt.get('name', oss_key)}.

---
*Data sourced {month}. Verify current pricing at {prop.get('website', '')} and {alt.get('website', '')}.*

Return ONLY the Markdown content. No preamble."""


# ──────────────────────────────────────────────────────────────
# AI PROVIDER 1: GROQ (FREE — primary)
# ──────────────────────────────────────────────────────────────
def generate_with_groq(prompt: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError('GROQ_API_KEY not set')
    response = requests.post(
        'https://api.groq.com/openai/v1/chat/completions',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={
            'model': 'llama-3.3-70b-versatile',
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 1200,
            'temperature': 0.6
        },
        timeout=30
    )
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content']


# ──────────────────────────────────────────────────────────────
# AI PROVIDER 2: GOOGLE GEMINI FLASH (FREE — fallback)
# ──────────────────────────────────────────────────────────────
def generate_with_gemini(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError('GEMINI_API_KEY not set')
    response = requests.post(
        f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}',
        headers={'Content-Type': 'application/json'},
        json={'contents': [{'parts': [{'text': prompt}]}]},
        timeout=30
    )
    response.raise_for_status()
    return response.json()['candidates'][0]['content']['parts'][0]['text']


# ──────────────────────────────────────────────────────────────
# FALLBACK: RICH TEMPLATE ENGINE (no API required — always works)
# ──────────────────────────────────────────────────────────────
TEMPLATE_DETAILS = {
    ('slack', 'element'): {
        'overview': "Slack is the dominant workplace messaging platform, used by millions of teams worldwide for channel-based communication. Element is a decentralized, end-to-end encrypted alternative built on the open Matrix protocol — giving teams full control over their data and communications infrastructure.",
        'differences': [
            "**Cost**: Slack charges $7.25–$15 per user per month; Element is free to self-host with no per-user fees",
            "**Data ownership**: Element runs on your own servers — Slack stores all your messages on Salesforce's infrastructure",
            "**Encryption**: Element provides end-to-end encryption by default; Slack encrypts in transit but not end-to-end",
            "**Federation**: Element can communicate across different Matrix servers; Slack is a closed silo",
            "**Integrations**: Slack has 2,400+ app integrations; Element's ecosystem is smaller but growing rapidly"
        ],
        'when_prop': "Slack is the right choice when your team values ease of setup, has a large budget, and relies heavily on third-party integrations like Salesforce, Zoom, or Google Workspace.",
        'when_oss': "Element is ideal for security-conscious teams, organizations with strict data residency requirements, or teams that want to eliminate per-seat SaaS costs at scale.",
        'migration': "Export Slack message history via Slack's data export, import into Mattermost (which has a Slack import tool), or start fresh in Element by recreating your channel structure."
    },
    ('slack', 'mattermost'): {
        'overview': "Slack is the leading proprietary team messaging platform offering rich integrations and a polished UI. Mattermost is an open-source alternative built specifically for developer and DevOps teams, offering a familiar Slack-like experience with full self-hosting control.",
        'differences': [
            "**Cost**: Slack costs $7.25–$15/user/month; Mattermost self-hosted is free with optional paid support",
            "**Deployment**: Mattermost can be deployed on your own servers, private cloud, or air-gapped environments",
            "**DevOps integration**: Mattermost has deeper native CI/CD and DevOps workflow integration than Slack",
            "**Data control**: All messages stay on your infrastructure with Mattermost; Slack data lives on third-party servers",
            "**Customization**: Mattermost's open-source codebase can be modified; Slack's cannot"
        ],
        'when_prop': "Slack is best when your team prioritizes ease of onboarding, has a large budget, and wants the widest ecosystem of third-party app integrations.",
        'when_oss': "Mattermost excels for engineering teams, regulated industries (healthcare, finance, defense), or organizations needing air-gapped deployment and custom integrations.",
        'migration': "Mattermost provides an official Slack import script. Export your Slack workspace data, run the importer, and recreate your integrations using Mattermost's equivalent webhook and bot APIs."
    },
    ('notion', 'appflowy'): {
        'overview': "Notion is a popular all-in-one workspace combining notes, wikis, databases, and project management in a flexible, block-based editor. AppFlowy is an open-source alternative with a similar philosophy but a local-first architecture that keeps your data on your device or your own server.",
        'differences': [
            "**Cost**: Notion costs $8–$20/user/month; AppFlowy is completely free",
            "**Data location**: AppFlowy stores data locally by default — Notion stores everything on their servers",
            "**Offline support**: AppFlowy works fully offline; Notion requires internet for most features",
            "**Privacy**: AppFlowy does not collect usage data; Notion's privacy policy allows data analysis",
            "**Feature parity**: Notion has more polished features and AI tools; AppFlowy is rapidly catching up"
        ],
        'when_prop': "Notion suits teams that want a polished, feature-rich workspace with AI writing tools, a wide template library, and seamless collaboration without managing infrastructure.",
        'when_oss': "AppFlowy is ideal for privacy-conscious individuals or teams, users in regions with data sovereignty requirements, or anyone who needs offline-first functionality.",
        'migration': "Export your Notion workspace as Markdown + CSV files, then import the Markdown files into AppFlowy. Database structures will need to be recreated manually."
    },
    ('github', 'gitlab'): {
        'overview': "GitHub is the world's largest code hosting platform, owned by Microsoft, with 100 million developers and an unmatched ecosystem. GitLab is a complete DevOps platform that can be fully self-hosted, offering everything from Git hosting to CI/CD, security scanning, and container registries in one application.",
        'differences': [
            "**Cost**: GitHub free tier is generous; GitLab Community Edition is fully free to self-host",
            "**CI/CD**: GitLab has more powerful built-in CI/CD pipelines; GitHub Actions is catching up",
            "**Self-hosting**: GitLab is designed to be self-hosted; GitHub Enterprise self-hosted is expensive",
            "**Feature scope**: GitLab is a complete DevSecOps platform; GitHub focuses on developer collaboration",
            "**Community size**: GitHub has a dramatically larger open-source community and project discoverability"
        ],
        'when_prop': "GitHub is the right choice for open-source projects that want maximum community visibility, or teams deeply integrated with the GitHub ecosystem and Actions workflows.",
        'when_oss': "GitLab self-hosted is ideal for enterprises needing full control over their DevOps stack, regulated industries, or teams wanting to consolidate multiple tools into one platform.",
        'migration': "GitLab provides a GitHub importer that migrates repositories, issues, PRs, wikis, and milestones. Update CI configuration from GitHub Actions syntax to GitLab CI/CD YAML format."
    },
    ('figma', 'penpot'): {
        'overview': "Figma is the dominant browser-based collaborative design tool, recently acquired by Adobe, used by most professional UI/UX teams. Penpot is an open-source design and prototyping platform that also runs in the browser and uses open SVG-based file formats instead of proprietary formats.",
        'differences': [
            "**Cost**: Figma charges $12–$75/user/month; Penpot is free to use on penpot.app or self-host",
            "**File format**: Penpot uses open SVG-based formats; Figma uses a proprietary binary format causing vendor lock-in",
            "**Collaboration**: Both support real-time collaboration; Figma's is more polished currently",
            "**Plugin ecosystem**: Figma has thousands of plugins; Penpot's library is smaller but growing",
            "**Vendor risk**: Adobe's acquisition of Figma (later blocked) highlighted vendor dependency risks"
        ],
        'when_prop': "Figma is the right choice for professional design teams that need the most polished toolset, the largest plugin ecosystem, and seamless handoff with tools like Zeplin or Storybook.",
        'when_oss': "Penpot is ideal for teams concerned about vendor lock-in, organizations with data privacy requirements, or budget-conscious teams that cannot justify per-seat design tool costs.",
        'migration': "Export Figma designs as SVG files, which can be imported into Penpot. Complex components and auto-layout features will require some manual recreation in Penpot's equivalent system."
    },
    ('jira', 'plane'): {
        'overview': "Jira is the industry-standard issue and project tracking tool from Atlassian, used extensively for agile software development. Plane is a modern open-source alternative with a clean, fast interface that supports Issues, Cycles (Sprints), Modules (Epics), and Pages.",
        'differences': [
            "**Cost**: Jira charges $7.75–$14.50/user/month; Plane is free to self-host",
            "**Complexity**: Jira is notoriously complex and slow; Plane is designed to be intuitive and fast",
            "**Customization**: Jira has extensive workflow customization; Plane's is simpler but improving",
            "**Integrations**: Jira integrates with the entire Atlassian ecosystem; Plane offers REST API access",
            "**Performance**: Plane's modern architecture delivers significantly faster page loads than Jira"
        ],
        'when_prop': "Jira is the right choice for large enterprises already invested in the Atlassian ecosystem (Confluence, Bitbucket), or teams that need highly customized workflow automation.",
        'when_oss': "Plane is ideal for startups, small-to-mid teams tired of Jira's complexity, or organizations wanting a clean issue tracker without per-seat licensing costs.",
        'migration': "Export Jira issues as CSV, then import into Plane using the CSV importer. Custom fields, automations, and advanced workflow rules will need to be recreated."
    },
    ('trello', 'wekan'): {
        'overview': "Trello is Atlassian's visual kanban board tool — simple, beginner-friendly, and widely used for personal and team task management. WeKan is an open-source kanban board that can be self-hosted, offering the same card/list/board model without vendor dependency.",
        'differences': [
            "**Cost**: Trello's free tier is limited; paid plans start at $5/user/month. WeKan is completely free",
            "**Data control**: WeKan runs on your own server; Trello data lives on Atlassian's infrastructure",
            "**Features**: Trello has a larger Power-Ups (integrations) marketplace; WeKan covers core kanban features",
            "**Setup**: Trello requires zero setup; WeKan requires a server to self-host",
            "**Customization**: WeKan's open-source code can be extended; Trello cannot be modified"
        ],
        'when_prop': "Trello is best for individuals and small teams wanting an instant, zero-setup kanban board with integrations to tools like Slack, Google Drive, and GitHub.",
        'when_oss': "WeKan is ideal for teams wanting full data ownership, self-hosted deployments, or organizations that need to run project management tools in air-gapped environments.",
        'migration': "Export Trello boards as JSON, then use WeKan's Trello importer (Settings → Import/Export) to recreate boards, lists, and cards with attachments."
    },
    ('dropbox', 'nextcloud'): {
        'overview': "Dropbox is one of the original cloud storage services, offering simple file sync and sharing across devices. Nextcloud is the world's most popular self-hosted cloud platform — combining file storage, sharing, calendar, contacts, video calls, and 400+ apps in one open-source package.",
        'differences': [
            "**Cost**: Dropbox charges $9.99–$16.58/user/month; Nextcloud is free to self-host (server costs only)",
            "**Storage limits**: Nextcloud storage is limited only by your server's disk space",
            "**Feature breadth**: Nextcloud is far more than storage — it's a full Google Workspace alternative",
            "**Privacy**: Nextcloud on your own server means only you can access your data",
            "**Setup complexity**: Dropbox is instant; Nextcloud requires server setup (Docker makes this easier)"
        ],
        'when_prop': "Dropbox is ideal for individuals or small teams wanting simple, reliable file sync with no infrastructure to manage and seamless integrations with Office and Slack.",
        'when_oss': "Nextcloud is the right choice for privacy-focused individuals, families, and organizations that want to eliminate cloud subscription costs and keep data on their own hardware.",
        'migration': "Download all Dropbox files locally, then upload to Nextcloud via the web interface or desktop sync client. Install the Nextcloud desktop app to maintain ongoing sync."
    },
    ('zoom', 'jitsi'): {
        'overview': "Zoom is the world's most widely used video conferencing platform, known for reliability and ease of use. Jitsi Meet is a fully open-source alternative that runs in the browser with no account required — and can be self-hosted for complete privacy.",
        'differences': [
            "**Cost**: Zoom free tier limits meetings to 40 minutes; Jitsi Meet is completely free with no time limits",
            "**Account requirement**: Jitsi Meet requires no account for participants; Zoom requires app install or account",
            "**Privacy**: Self-hosted Jitsi is fully private; Zoom has had multiple privacy controversies",
            "**Features**: Zoom has more enterprise features (webinars, phone, AI tools); Jitsi covers core video needs",
            "**Self-hosting**: Jitsi can be deployed on a small VPS in minutes; Zoom cannot be self-hosted"
        ],
        'when_prop': "Zoom is the right choice for large organizations needing webinar features, enterprise phone systems, AI meeting summaries, and compliance with SOC2/HIPAA requirements.",
        'when_oss': "Jitsi Meet is ideal for small teams, privacy-conscious users, educational institutions, or anyone who wants to host quick meetings without requiring participants to install software.",
        'migration': "No migration needed — Jitsi is a drop-in replacement. Share a Jitsi meeting link instead of a Zoom link. For recurring meetings, replace Zoom calendar links with Jitsi room URLs."
    },
}


def generate_with_template(prop_key: str, oss_key: str) -> str:
    """Rich template-based comparison. Works with zero API access."""
    prop = TOOLS.get(prop_key, {})
    alt  = TOOLS.get(oss_key,  {})
    month = datetime.now().strftime('%B %Y')
    pair_key = (prop_key, oss_key)
    
    # Get detailed content if available, else generate generic
    details = TEMPLATE_DETAILS.get(pair_key)
    
    if details:
        overview = details['overview']
        diff_bullets = '\n'.join(f'- {d}' for d in details['differences'])
        when_prop = details['when_prop']
        when_oss  = details['when_oss']
        migration = details['migration']
    else:
        overview = f"{prop.get('description', prop.get('name', prop_key))} is a popular proprietary tool in the {prop.get('category', 'software')} space. {alt.get('name', oss_key)} is a free, open-source alternative that gives organizations complete control over their data and deployment."
        diff_bullets = f"""- **Cost**: {prop.get('name', prop_key)} costs {prop.get('pricing', 'see website')} per user; {alt.get('name', oss_key)} is {alt.get('pricing', 'free')}
- **License**: {prop.get('name', prop_key)} is {prop.get('license', 'proprietary')}; {alt.get('name', oss_key)} is licensed under {alt.get('license', 'an open-source license')}
- **Data ownership**: {alt.get('name', oss_key)} can be self-hosted, meaning your data stays on infrastructure you control
- **Vendor lock-in**: {alt.get('name', oss_key)} eliminates dependency on a single commercial vendor
- **Community**: {alt.get('name', oss_key)} has an active open-source community contributing features and fixes"""
        when_prop = f"{prop.get('name', prop_key)} is the right choice when you need the most polished user experience, the broadest integration ecosystem, and professional support with SLA guarantees."
        when_oss  = f"{alt.get('name', oss_key)} is ideal for privacy-conscious teams, organizations with strict data sovereignty requirements, or anyone wanting to eliminate per-seat subscription costs at scale."
        migration = f"Export your data from {prop.get('name', prop_key)} in its standard export format, review {alt.get('name', oss_key)}'s import documentation, and plan for a pilot period where both tools run in parallel."

    # Build cost at scale table
    prop_price_raw = prop.get('pricing', '$0')
    try:
        price_per_user = float(''.join(c for c in prop_price_raw.split('–')[0].split('/')[0] if c.isdigit() or c == '.'))
        cost_50 = f"~${price_per_user * 50:,.0f}/month"
        cost_200 = f"~${price_per_user * 200:,.0f}/month"
    except:
        cost_50 = "See pricing page"
        cost_200 = "See pricing page"

    github_badge = f"\n> 📦 GitHub: [{alt.get('github', '')}](https://github.com/{alt.get('github', '')}) · ⭐ ~{alt.get('stars_approx', 'N/A')} stars" if alt.get('github') else ""

    return f"""# {prop.get('name', prop_key)} vs {alt.get('name', oss_key)}

## Overview

{overview}

## Key Differences

{diff_bullets}

## Pricing Comparison

| Aspect | {prop.get('name', prop_key)} | {alt.get('name', oss_key)} |
|--------|-------------------------------|-------------------------------|
| Base pricing | {prop.get('pricing', 'N/A')} | {alt.get('pricing', 'Free')} |
| License | {prop.get('license', 'Proprietary')} | {alt.get('license', 'Open Source')} |
| Self-hosting | ❌ Not available | ✅ Available |
| Cost at 50 users | {cost_50} | $0/month (self-hosted) |
| Cost at 200 users | {cost_200} | $0/month (self-hosted) |
| Vendor lock-in | High | None |

## Pros and Cons

### {prop.get('name', prop_key)}

**Pros:**
- Polished, professionally designed user interface
- Large ecosystem of official integrations
- Managed infrastructure — no server maintenance required
- Enterprise SLA and dedicated support available
- Mobile apps are well-maintained and reliable

**Cons:**
- Significant per-user monthly cost that scales linearly with team size
- Your data is stored on the vendor's infrastructure
- No ability to inspect or modify the source code
- Feature roadmap controlled entirely by the vendor
- Risk of pricing changes, acquisition, or discontinuation

### {alt.get('name', oss_key)}

**Pros:**
- Free to self-host — costs only server infrastructure
- Complete data ownership and privacy control
- Source code is auditable and modifiable
- Active open-source community
- No vendor lock-in or risk of sudden pricing changes{github_badge}

**Cons:**
- Requires technical knowledge to self-host and maintain
- May lack some advanced features found in the proprietary version
- Support relies on community forums rather than a paid helpdesk
- UI polish may lag behind the proprietary tool
- You are responsible for updates, backups, and security patches

## When to Choose Each

**Choose {prop.get('name', prop_key)} if:** {when_prop}

**Choose {alt.get('name', oss_key)} if:** {when_oss}

## Migration Path

{migration}

---
*Data sourced {month}. Pricing and features change — verify at [{prop.get('name', prop_key)}]({prop.get('website', '')}) and [{alt.get('name', oss_key)}]({alt.get('website', '')}) before making decisions.*
"""


# ──────────────────────────────────────────────────────────────
# MAIN GENERATION FUNCTION — waterfall: Groq → Gemini → Template
# ──────────────────────────────────────────────────────────────
def generate_comparison(prop_key: str, oss_key: str) -> Dict:
    prompt = build_prompt(prop_key, oss_key)
    prop = TOOLS.get(prop_key, {})
    alt  = TOOLS.get(oss_key,  {})
    content = None
    provider_used = None

    try:
        content = generate_with_groq(prompt)
        provider_used = 'groq'
        logger.info(f"    ✅ Generated with Groq")
    except Exception as e:
        logger.warning(f"    ⚠️  Groq unavailable ({type(e).__name__}) — trying Gemini...")
        time.sleep(1)

    if content is None:
        try:
            content = generate_with_gemini(prompt)
            provider_used = 'gemini'
            logger.info(f"    ✅ Generated with Gemini")
        except Exception as e:
            logger.warning(f"    ⚠️  Gemini unavailable ({type(e).__name__}) — using template...")

    if content is None:
        content = generate_with_template(prop_key, oss_key)
        provider_used = 'template'
        logger.info(f"    ✅ Generated with template engine")

    prop_pricing = prop.get('pricing', 'N/A')
    oss_pricing  = alt.get('pricing', 'Free')

    return {
        'id': f'{prop_key}-vs-{oss_key}',
        'slug': f'{prop_key}-vs-{oss_key}',
        'title': f"{prop.get('name', prop_key)} vs {alt.get('name', oss_key)}",
        'proprietary_tool': prop.get('name', prop_key),
        'proprietary_key': prop_key,
        'oss_tool': alt.get('name', oss_key),
        'oss_key': oss_key,
        'category': alt.get('category', 'general'),
        'proprietary_pricing': prop_pricing,
        'oss_pricing': oss_pricing,
        'proprietary_website': prop.get('website', ''),
        'oss_website': alt.get('website', ''),
        'oss_github': alt.get('github', ''),
        'oss_stars': alt.get('stars_approx', ''),
        'comparison_markdown': content,
        'provider': provider_used,
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'status': 'generated'
    }


def main():
    parser = argparse.ArgumentParser(description='Generate AI comparisons')
    parser.add_argument('--index', '-i', type=int, default=1)
    parser.add_argument('--output', '-o', default='.cache/publish')
    parser.add_argument('--dlq-dir', '-d', default='./dlq')
    args = parser.parse_args()

    Path(args.output).mkdir(parents=True, exist_ok=True)
    dlq = DeadLetterQueue(args.dlq_dir)

    start = (args.index - 1) * 10
    batch = COMPARISON_PAIRS[start:start + 10]

    if not batch:
        max_batch = (len(COMPARISON_PAIRS) // 10) + 1
        logger.warning(f"No comparisons in batch {args.index}. Max index: {max_batch}")
        return

    logger.info(f"🎯 Generating batch {args.index}: {len(batch)} comparisons...")
    generated = []
    failed = []

    for prop_key, oss_key in batch:
        prop_name = TOOLS.get(prop_key, {}).get('name', prop_key)
        oss_name  = TOOLS.get(oss_key,  {}).get('name', oss_key)
        logger.info(f"  ⚙️  {prop_name} vs {oss_name}")
        try:
            result = generate_comparison(prop_key, oss_key)
            generated.append(result)
            time.sleep(0.3)
        except Exception as e:
            logger.error(f"  ❌ Failed: {prop_key} vs {oss_key}: {e}")
            failed.append({'proprietary': prop_key, 'oss': oss_key, 'error': str(e)})
            dlq.save_failed({'type': 'comparison', 'proprietary': prop_key, 'oss': oss_key}, e)

    if generated:
        out_path = Path(args.output) / f'comparisons_{args.index}.json'
        with open(out_path, 'w') as f:
            json.dump(generated, f, indent=2)
        logger.info(f"  💾 Saved {len(generated)} comparisons → {out_path}")

    logger.info('=' * 60)
    logger.info(f"  ✅ Generated: {len(generated)}  |  ❌ Failed: {len(failed)}")
    if failed:
        send_slack_alert(f"⚠️ {len(failed)} comparisons failed in batch {args.index}", "warning")


if __name__ == "__main__":
    main()
