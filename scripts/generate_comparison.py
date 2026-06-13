#!/usr/bin/env python3
"""
generate_comparison.py
Generates AI comparison pages using free APIs:
  Primary:  Groq (llama-3.3-70b-versatile) — free, fast
  Fallback: Google Gemini Flash             — free, reliable
  Last:     Template engine                 — always works, no API needed

Usage: python scripts/generate_comparison.py --index 1
"""

import argparse, json, logging, os, re, sys, time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import random
import requests

sys.path.insert(0, str(Path(__file__).parent))
from utils_resilience import CircuitBreaker, DeadLetterQueue, send_slack_alert

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)

TOOLS = {
    'slack':           {'name': 'Slack',           'category': 'communication',      'pricing': '$7.25-$15/user/month',    'license': 'Proprietary',               'website': 'https://slack.com',           'description': 'Team messaging platform with channels, DMs, and thousands of integrations.',           'founded': '2013', 'company': 'Salesforce'},
    'element':         {'name': 'Element',          'category': 'communication',      'pricing': 'Free (self-hosted)',       'license': 'Apache 2.0',                'website': 'https://element.io',          'description': 'Decentralized, end-to-end encrypted messaging built on the open Matrix protocol.',                         'github': 'element-hq/element-web',  'stars_approx': '11k'},
    'mattermost':      {'name': 'Mattermost',       'category': 'communication',      'pricing': 'Free (self-hosted)',       'license': 'MIT / AGPL',                'website': 'https://mattermost.com',      'description': 'Open-source workplace messaging built for developers and DevOps teams.',                                     'github': 'mattermost/mattermost',   'stars_approx': '30k'},
    'notion':          {'name': 'Notion',           'category': 'productivity',       'pricing': '$8-$20/user/month',       'license': 'Proprietary',               'website': 'https://notion.so',           'description': 'All-in-one workspace combining notes, databases, wikis, and project management.',   'founded': '2016', 'company': 'Notion Labs'},
    'appflowy':        {'name': 'AppFlowy',         'category': 'productivity',       'pricing': 'Free',                    'license': 'GPL 3.0',                   'website': 'https://appflowy.io',         'description': 'Open-source Notion alternative with local-first storage, offline support, and strong privacy guarantees.',                     'github': 'AppFlowy-IO/AppFlowy',    'stars_approx': '59k'},
    'obsidian':        {'name': 'Obsidian',         'category': 'productivity',       'pricing': 'Free (local use)',         'license': 'Proprietary (free personal)','website': 'https://obsidian.md',        'description': 'Local-first knowledge base using plain Markdown files.',       'founded': '2020', 'company': 'Dynalist Inc'},
    'logseq':          {'name': 'Logseq',           'category': 'productivity',       'pricing': 'Free',                    'license': 'AGPL 3.0',                  'website': 'https://logseq.com',          'description': 'Open-source outliner and knowledge management tool using plain text files.',                'github': 'logseq/logseq',           'stars_approx': '33k'},
    'github':          {'name': 'GitHub',           'category': 'developer-tools',    'pricing': 'Free / $7-$21/user',      'license': 'Proprietary',               'website': 'https://github.com',          'description': 'The world largest code hosting and collaboration platform. Owned by Microsoft since 2018.',                                   'founded': '2008', 'company': 'Microsoft'},
    'gitlab':          {'name': 'GitLab',           'category': 'developer-tools',    'pricing': 'Free (self-hosted)',       'license': 'MIT (CE)',                  'website': 'https://gitlab.com',          'description': 'Complete DevOps platform with built-in CI/CD, issue tracking, container registry, and more.',        'github': 'gitlabhq/gitlabhq',       'stars_approx': '24k'},
    'gitea':           {'name': 'Gitea',            'category': 'developer-tools',    'pricing': 'Free (self-hosted)',       'license': 'MIT',                       'website': 'https://gitea.io',            'description': 'Lightweight, fast self-hosted Git service. Very low memory footprint.',                     'github': 'go-gitea/gitea',          'stars_approx': '44k'},
    'figma':           {'name': 'Figma',            'category': 'design',             'pricing': '$12-$75/user/month',      'license': 'Proprietary',               'website': 'https://figma.com',           'description': 'Browser-based collaborative design and prototyping tool.',                            'founded': '2012', 'company': 'Adobe'},
    'penpot':          {'name': 'Penpot',           'category': 'design',             'pricing': 'Free',                    'license': 'MPL 2.0',                   'website': 'https://penpot.app',          'description': 'Open-source design and prototyping platform that works in the browser.',              'github': 'penpot/penpot',           'stars_approx': '33k'},
    'jira':            {'name': 'Jira',             'category': 'project-management', 'pricing': '$7.75-$14.50/user/month', 'license': 'Proprietary',               'website': 'https://atlassian.com/jira',  'description': 'Industry-leading issue and project tracking software for agile teams.',                       'founded': '2002', 'company': 'Atlassian'},
    'plane':           {'name': 'Plane',            'category': 'project-management', 'pricing': 'Free (self-hosted)',       'license': 'Apache 2.0',                'website': 'https://plane.so',            'description': 'Open-source project management tool designed as a Jira alternative.',                                   'github': 'makeplane/plane',         'stars_approx': '31k'},
    'linear':          {'name': 'Linear',           'category': 'project-management', 'pricing': 'Free / $8/user/month',    'license': 'Proprietary',               'website': 'https://linear.app',          'description': 'Streamlined issue tracker known for speed and keyboard-first design.',                    'founded': '2019', 'company': 'Linear'},
    'trello':          {'name': 'Trello',           'category': 'project-management', 'pricing': 'Free / $5+/user/month',   'license': 'Proprietary',               'website': 'https://trello.com',          'description': 'Visual kanban board tool with cards, lists, and boards.',                    'founded': '2011', 'company': 'Atlassian'},
    'wekan':           {'name': 'WeKan',            'category': 'project-management', 'pricing': 'Free (self-hosted)',       'license': 'MIT',                       'website': 'https://wekan.github.io',     'description': 'Open-source kanban board that can be self-hosted.',                  'github': 'wekan/wekan',             'stars_approx': '20k'},
    'dropbox':         {'name': 'Dropbox',          'category': 'file-storage',       'pricing': '$9.99-$16.58/user/month', 'license': 'Proprietary',               'website': 'https://dropbox.com',         'description': 'Pioneer cloud file storage and sync service.',                                      'founded': '2007', 'company': 'Dropbox Inc'},
    'nextcloud':       {'name': 'Nextcloud',        'category': 'file-storage',       'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://nextcloud.com',       'description': 'The most popular self-hosted cloud storage platform.',    'github': 'nextcloud/server',        'stars_approx': '27k'},
    'zoom':            {'name': 'Zoom',             'category': 'video-conferencing', 'pricing': 'Free / $13.33+/user/month','license': 'Proprietary',              'website': 'https://zoom.us',             'description': 'Dominant video conferencing platform since 2020.',                                     'founded': '2011', 'company': 'Zoom Video Communications'},
    'jitsi':           {'name': 'Jitsi Meet',       'category': 'video-conferencing', 'pricing': 'Free',                    'license': 'Apache 2.0',                'website': 'https://jitsi.org',           'description': 'Open-source video conferencing that works entirely in the browser.',                   'github': 'jitsi/jitsi-meet',        'stars_approx': '23k'},
    'discord':         {'name': 'Discord',          'category': 'communication',      'pricing': 'Free / $9.99/month',      'license': 'Proprietary',               'website': 'https://discord.com',         'description': 'Chat platform popular with gaming and developer communities.',                'founded': '2015', 'company': 'Discord Inc'},
    'zulip':           {'name': 'Zulip',            'category': 'communication',      'pricing': 'Free (self-hosted)',       'license': 'Apache 2.0',                'website': 'https://zulip.com',           'description': 'Open-source team chat with a unique threaded model.',                   'github': 'zulip/zulip',             'stars_approx': '21k'},
    'asana':           {'name': 'Asana',            'category': 'project-management', 'pricing': 'Free / $10.99+/user',     'license': 'Proprietary',               'website': 'https://asana.com',           'description': 'Work management platform for tracking tasks, projects, and team goals.',                       'founded': '2008', 'company': 'Asana Inc'},
    'taiga':           {'name': 'Taiga',            'category': 'project-management', 'pricing': 'Free (self-hosted)',       'license': 'MPL 2.0',                   'website': 'https://taiga.io',            'description': 'Open-source agile project management tool supporting Scrum, Kanban, and Scrumban boards.',                                    'github': 'taigaio/taiga-back',      'stars_approx': '8k'},
    'microsoft-teams': {'name': 'Microsoft Teams',  'category': 'communication',      'pricing': 'Free / $6-$22/user/month','license': 'Proprietary',               'website': 'https://microsoft.com/teams', 'description': 'Microsoft workplace chat and video conferencing platform.',  'founded': '2017', 'company': 'Microsoft'},
    'google-workspace':{'name': 'Google Workspace', 'category': 'productivity',       'pricing': '$6-$18/user/month',       'license': 'Proprietary',               'website': 'https://workspace.google.com','description': 'Google suite of cloud productivity tools including Gmail, Drive, Docs, Sheets, Meet, and Calendar.',                          'founded': '2006', 'company': 'Google'},
    'airtable':        {'name': 'Airtable',         'category': 'productivity',       'pricing': 'Free / $10-$20/user/month','license': 'Proprietary',              'website': 'https://airtable.com',        'description': 'Flexible spreadsheet-database hybrid for organizing anything.',     'founded': '2012', 'company': 'Airtable Inc'},
    'nocodb':          {'name': 'NocoDB',           'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://nocodb.com',          'description': 'Open-source Airtable alternative that turns any database into a smart spreadsheet.',        'github': 'nocodb/nocodb',           'stars_approx': '45k'},
    'monday':          {'name': 'Monday.com',       'category': 'project-management', 'pricing': '$9-$19/user/month',       'license': 'Proprietary',               'website': 'https://monday.com',          'description': 'Visual work management platform used by 180,000+ organizations.',          'founded': '2012', 'company': 'monday.com Ltd'},
    'hubspot':         {'name': 'HubSpot',          'category': 'productivity',       'pricing': 'Free / $15-$800+/month',  'license': 'Proprietary',               'website': 'https://hubspot.com',         'description': 'All-in-one CRM, marketing, sales, and customer service platform.',                     'founded': '2006', 'company': 'HubSpot Inc'},
    'suitecrm':        {'name': 'SuiteCRM',         'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://suitecrm.com',        'description': 'The world most popular open-source CRM. A full-featured fork of SugarCRM.',                   'github': 'salesagility/SuiteCRM',   'stars_approx': '4k'},
    'mailchimp':       {'name': 'Mailchimp',        'category': 'productivity',       'pricing': 'Free / $13-$350+/month',  'license': 'Proprietary',               'website': 'https://mailchimp.com',       'description': 'Leading email marketing platform with automation, landing pages, and analytics.',              'founded': '2001', 'company': 'Intuit'},
    'listmonk':        {'name': 'Listmonk',         'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://listmonk.app',        'description': 'High-performance, self-hosted newsletter and mailing list manager.',        'github': 'knadh/listmonk',          'stars_approx': '15k'},
    'wordpress-com':   {'name': 'WordPress.com',    'category': 'productivity',       'pricing': 'Free / $4-$45+/month',    'license': 'Proprietary',               'website': 'https://wordpress.com',       'description': 'Hosted blogging and website platform.',               'founded': '2005', 'company': 'Automattic'},
    'ghost':           {'name': 'Ghost',            'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'MIT',                       'website': 'https://ghost.org',           'description': 'Open-source publishing platform built for professional bloggers and creators.',            'github': 'TryGhost/Ghost',          'stars_approx': '47k'},
    'confluence':      {'name': 'Confluence',       'category': 'productivity',       'pricing': '$5.75-$11/user/month',    'license': 'Proprietary',               'website': 'https://atlassian.com/confluence', 'description': 'Team wiki and documentation tool from Atlassian.',       'founded': '2004', 'company': 'Atlassian'},
    'bookstack':       {'name': 'BookStack',        'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'MIT',                       'website': 'https://bookstackapp.com',    'description': 'Simple, self-hosted wiki platform for organizing documentation.',         'github': 'BookStackApp/BookStack',  'stars_approx': '15k'},
    'zendesk':         {'name': 'Zendesk',          'category': 'productivity',       'pricing': '$19-$115/user/month',     'license': 'Proprietary',               'website': 'https://zendesk.com',         'description': 'Leading customer support and ticketing platform.',          'founded': '2007', 'company': 'Zendesk Inc'},
    'zammad':          {'name': 'Zammad',           'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://zammad.org',          'description': 'Open-source helpdesk and customer support ticketing system.',               'github': 'zammad/zammad',           'stars_approx': '4k'},
    'calendly':        {'name': 'Calendly',         'category': 'productivity',       'pricing': 'Free / $8-$16/user/month','license': 'Proprietary',               'website': 'https://calendly.com',        'description': 'Popular scheduling automation tool.',               'founded': '2013', 'company': 'Calendly LLC'},
    'cal-com':         {'name': 'Cal.com',          'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://cal.com',             'description': 'Open-source Calendly alternative for scheduling.',      'github': 'calcom/cal.com',          'stars_approx': '32k'},
    'intercom':        {'name': 'Intercom',         'category': 'communication',      'pricing': '$39-$139+/month',         'license': 'Proprietary',               'website': 'https://intercom.com',        'description': 'Customer messaging platform for sales, marketing, and support.',        'founded': '2011', 'company': 'Intercom Inc'},
    'chatwoot':        {'name': 'Chatwoot',         'category': 'communication',      'pricing': 'Free (self-hosted)',       'license': 'MIT',                       'website': 'https://chatwoot.com',        'description': 'Open-source customer support platform supporting live chat, email, and social channels.',                    'github': 'chatwoot/chatwoot',       'stars_approx': '22k'},
    'postman':         {'name': 'Postman',          'category': 'developer-tools',    'pricing': 'Free / $14-$29/user/month','license': 'Proprietary',              'website': 'https://postman.com',         'description': 'The most widely used API development and testing platform.',                      'founded': '2014', 'company': 'Postman Inc'},
    'hoppscotch':      {'name': 'Hoppscotch',       'category': 'developer-tools',    'pricing': 'Free (self-hosted)',       'license': 'MIT',                       'website': 'https://hoppscotch.io',       'description': 'Lightweight open-source API development tool.',             'github': 'hoppscotch/hoppscotch',   'stars_approx': '65k'},
    '1password':       {'name': '1Password',        'category': 'productivity',       'pricing': '$2.99-$7.99/user/month',  'license': 'Proprietary',               'website': 'https://1password.com',       'description': 'Leading password manager for individuals and teams.',        'founded': '2006', 'company': 'AgileBits'},
    'bitwarden':       {'name': 'Bitwarden',        'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://bitwarden.com',       'description': 'Open-source password manager that can be self-hosted.',           'github': 'bitwarden/server',        'stars_approx': '15k'},
    'adobe-photoshop': {'name': 'Adobe Photoshop',  'category': 'design',             'pricing': '$20.99-$54.99/month',     'license': 'Proprietary',               'website': 'https://adobe.com/photoshop', 'description': 'Industry-standard image editing software by Adobe.',            'founded': '1988', 'company': 'Adobe'},
    'gimp':            {'name': 'GIMP',             'category': 'design',             'pricing': 'Free',                    'license': 'GPL 3.0',                   'website': 'https://gimp.org',            'description': 'The GNU Image Manipulation Program. Powerful open-source image editor.',                    'github': 'GNOME/gimp',              'stars_approx': '4k'},
    'typeform':        {'name': 'Typeform',         'category': 'productivity',       'pricing': 'Free / $25-$83/month',    'license': 'Proprietary',               'website': 'https://typeform.com',        'description': 'Conversational form and survey tool known for its beautiful, interactive design.',             'founded': '2012', 'company': 'Typeform'},
    'formbricks':      {'name': 'Formbricks',       'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://formbricks.com',      'description': 'Open-source survey and form tool.',              'github': 'formbricks/formbricks',   'stars_approx': '9k'},
    'miro':            {'name': 'Miro',             'category': 'design',             'pricing': 'Free / $8-$16/user/month','license': 'Proprietary',               'website': 'https://miro.com',            'description': 'Online collaborative whiteboard platform.',             'founded': '2011', 'company': 'RealtimeBoard'},
    'excalidraw':      {'name': 'Excalidraw',       'category': 'design',             'pricing': 'Free',                    'license': 'MIT',                       'website': 'https://excalidraw.com',      'description': 'Open-source virtual whiteboard with a hand-drawn feel.',                   'github': 'excalidraw/excalidraw',   'stars_approx': '90k'},
    'netlify':         {'name': 'Netlify',          'category': 'developer-tools',    'pricing': 'Free / $19-$99/month',    'license': 'Proprietary',               'website': 'https://netlify.com',         'description': 'Popular platform for deploying and hosting web apps and static sites.',            'founded': '2014', 'company': 'Netlify Inc'},
    'coolify':         {'name': 'Coolify',          'category': 'developer-tools',    'pricing': 'Free (self-hosted)',       'license': 'Apache 2.0',                'website': 'https://coolify.io',          'description': 'Open-source self-hostable platform for deploying apps, databases, and services.',      'github': 'coollabsio/coolify',      'stars_approx': '35k'},
    'salesforce':      {'name': 'Salesforce',        'category': 'productivity',       'pricing': '$25-$300+/user/month',    'license': 'Proprietary',               'website': 'https://salesforce.com',      'description': 'The world leading CRM platform.',               'founded': '1999', 'company': 'Salesforce Inc'},
    'espocrm':         {'name': 'EspoCRM',           'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://espocrm.com',         'description': 'Open-source CRM with a clean interface covering sales, contacts, leads, and reporting.',                'github': 'espocrm/espocrm',         'stars_approx': '2k'},
    'zoho-crm':        {'name': 'Zoho CRM',         'category': 'productivity',       'pricing': '$14-$52/user/month',      'license': 'Proprietary',               'website': 'https://zoho.com/crm',        'description': 'Feature-rich CRM platform from Zoho suite, popular with SMBs worldwide.',              'founded': '1996', 'company': 'Zoho Corporation'},
    'vtiger':          {'name': 'Vtiger CRM',        'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'VPL / Open Source',         'website': 'https://vtiger.com',          'description': 'Open-source CRM with sales, marketing, and support modules plus a strong self-hosted community edition.', 'github': 'vtiger-crm/vtiger7', 'stars_approx': '1k'},
    'dolibarr':        {'name': 'Dolibarr',          'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'GPL 3.0',                   'website': 'https://dolibarr.org',        'description': 'All-in-one open-source ERP and CRM for SMBs covering invoicing, accounting, stock, and customer management.', 'github': 'Dolibarr/dolibarr', 'stars_approx': '5k'},
    'grammarly':       {'name': 'Grammarly',         'category': 'productivity',       'pricing': 'Free / $12-$15/month',    'license': 'Proprietary',               'website': 'https://grammarly.com',       'description': 'AI-powered writing assistant that checks grammar, spelling, style, and tone.',              'founded': '2009', 'company': 'Grammarly Inc'},
    'languagetool':    {'name': 'LanguageTool',      'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'LGPL 2.1',                  'website': 'https://languagetool.org',    'description': 'Open-source grammar and spell checker supporting 30+ languages.',         'github': 'languagetool-org/languagetool', 'stars_approx': '12k'},
    'shopify':         {'name': 'Shopify',           'category': 'productivity',       'pricing': '$29-$299+/month',         'license': 'Proprietary',               'website': 'https://shopify.com',         'description': 'Leading e-commerce platform powering 4 million+ online stores.',               'founded': '2006', 'company': 'Shopify Inc'},
    'woocommerce':     {'name': 'WooCommerce',       'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'GPL 3.0',                   'website': 'https://woocommerce.com',     'description': 'The world most popular open-source e-commerce plugin for WordPress.',                  'github': 'woocommerce/woocommerce',  'stars_approx': '9k'},
    'lastpass':        {'name': 'LastPass',          'category': 'productivity',       'pricing': 'Free / $3-$4/user/month', 'license': 'Proprietary',               'website': 'https://lastpass.com',        'description': 'Popular cloud-based password manager.',                              'founded': '2008', 'company': 'GoTo'},
    'vaultwarden':     {'name': 'Vaultwarden',       'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://github.com/dani-garcia/vaultwarden', 'description': 'Lightweight self-hosted Bitwarden-compatible server.', 'github': 'dani-garcia/vaultwarden',  'stars_approx': '39k'},
    'quickbooks':      {'name': 'QuickBooks',        'category': 'productivity',       'pricing': '$30-$200+/month',         'license': 'Proprietary',               'website': 'https://quickbooks.intuit.com','description': 'Leading small business accounting software from Intuit.',    'founded': '1983', 'company': 'Intuit'},
    'akaunting':       {'name': 'Akaunting',         'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'GPL 3.0',                   'website': 'https://akaunting.com',       'description': 'Free, open-source accounting software for small businesses.',        'github': 'akaunting/akaunting',      'stars_approx': '8k'},
    'docusign':        {'name': 'DocuSign',          'category': 'productivity',       'pricing': '$15-$65+/user/month',     'license': 'Proprietary',               'website': 'https://docusign.com',        'description': 'The world leading e-signature platform.',    'founded': '2003', 'company': 'DocuSign Inc'},
    'docuseal':        {'name': 'DocuSeal',          'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://docuseal.co',         'description': 'Open-source DocuSign alternative for e-signatures and document completion.',       'github': 'docusealco/docuseal',      'stars_approx': '8k'},
    'sentry':          {'name': 'Sentry',            'category': 'developer-tools',    'pricing': 'Free / $26-$80+/month',   'license': 'Proprietary',               'website': 'https://sentry.io',           'description': 'Leading error tracking and application monitoring platform.',   'founded': '2012', 'company': 'Functional Software'},
    'glitchtip':       {'name': 'GlitchTip',         'category': 'developer-tools',    'pricing': 'Free (self-hosted)',       'license': 'BSD',                       'website': 'https://glitchtip.com',       'description': 'Open-source error tracking compatible with the Sentry SDK.',                             'github': 'glitchtip/glitchtip',      'stars_approx': '2k'},
    'hotjar':          {'name': 'Hotjar',            'category': 'productivity',       'pricing': 'Free / $32-$80+/month',   'license': 'Proprietary',               'website': 'https://hotjar.com',          'description': 'Behavior analytics tool with heatmaps, session recordings, and surveys.',                   'founded': '2014', 'company': 'Hotjar Ltd'},
    'openreplay':      {'name': 'OpenReplay',        'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://openreplay.com',      'description': 'Open-source session replay and product analytics suite.',             'github': 'openreplay/openreplay',    'stars_approx': '9k'},
    'loom':            {'name': 'Loom',              'category': 'communication',      'pricing': 'Free / $12.50-$14.99/user/month','license': 'Proprietary',          'website': 'https://loom.com',            'description': 'Screen and video recording tool for async communication.',             'founded': '2015', 'company': 'Loom Inc'},
    'cap':             {'name': 'Cap',               'category': 'communication',      'pricing': 'Free (self-hosted)',       'license': 'AGPL 3.0',                  'website': 'https://cap.so',              'description': 'Open-source screen recording and sharing tool.',       'github': 'CapSoftware/Cap',          'stars_approx': '8k'},
    'canva':           {'name': 'Canva',             'category': 'design',             'pricing': 'Free / $15-$30/user/month','license': 'Proprietary',               'website': 'https://canva.com',           'description': 'Popular web-based design platform for creating graphics, presentations, and marketing materials.', 'founded': '2013', 'company': 'Canva Pty Ltd'},
    'sketch':          {'name': 'Sketch',            'category': 'design',             'pricing': '$9-$20/user/month',       'license': 'Proprietary',               'website': 'https://sketch.com',          'description': 'Mac-only UI design tool popular with product designers.',                    'founded': '2010', 'company': 'Sketch BV'},
    'adobe-xd':        {'name': 'Adobe XD',          'category': 'design',             'pricing': '$54.99/month (CC)',       'license': 'Proprietary',               'website': 'https://adobe.com/xd',        'description': 'Adobe UI/UX design and prototyping tool. Being phased out in favor of Figma.',              'founded': '2016', 'company': 'Adobe'},
    'adobe-illustrator':{'name': 'Adobe Illustrator','category': 'design',             'pricing': '$20.99-$54.99/month',     'license': 'Proprietary',               'website': 'https://adobe.com/illustrator','description': 'Industry-standard vector graphics editor.',           'founded': '1987', 'company': 'Adobe'},
    'inkscape':        {'name': 'Inkscape',          'category': 'design',             'pricing': 'Free',                    'license': 'GPL 3.0',                   'website': 'https://inkscape.org',        'description': 'Powerful open-source vector graphics editor. Full SVG support.',          'github': 'inkscape/inkscape',        'stars_approx': '4k'},
    'adobe-premiere':  {'name': 'Adobe Premiere Pro','category': 'design',             'pricing': '$20.99-$54.99/month',     'license': 'Proprietary',               'website': 'https://adobe.com/premiere',  'description': 'Industry-leading professional video editing software.',      'founded': '1991', 'company': 'Adobe'},
    'kdenlive':        {'name': 'Kdenlive',          'category': 'design',             'pricing': 'Free',                    'license': 'GPL 2.0',                   'website': 'https://kdenlive.org',        'description': 'Powerful open-source video editor for Linux, Mac, and Windows.',       'github': 'KDE/kdenlive',             'stars_approx': '3k'},
    'framer':          {'name': 'Framer',            'category': 'design',             'pricing': 'Free / $15-$35/month',    'license': 'Proprietary',               'website': 'https://framer.com',          'description': 'Web design and prototyping tool with advanced animations.',       'founded': '2013', 'company': 'Framer BV'},
    'plasmic':         {'name': 'Plasmic',           'category': 'design',             'pricing': 'Free (self-hosted)',       'license': 'MIT',                       'website': 'https://plasmic.app',         'description': 'Open-source visual web builder and design tool.',   'github': 'plasmicapp/plasmic',       'stars_approx': '4k'},
    'slack-ai':        {'name': 'Slack AI',          'category': 'communication',      'pricing': '$10-$25/user/month',       'license': 'Proprietary',               'website': 'https://slack.com',           'description': 'Slack with AI features for summarisation and search.',               'founded': '2013', 'company': 'Salesforce'},
    'audacity':        {'name': 'Audacity',          'category': 'design',             'pricing': 'Free',                    'license': 'GPL 2.0',                   'website': 'https://audacityteam.org',    'description': 'Free open-source digital audio editor and recording software.',                    'github': 'audacity/audacity',        'stars_approx': '12k'},
    'adobe-audition':  {'name': 'Adobe Audition',    'category': 'design',             'pricing': '$20.99-$54.99/month',     'license': 'Proprietary',               'website': 'https://adobe.com/audition',  'description': 'Professional audio workstation from Adobe.',       'founded': '2003', 'company': 'Adobe'},
    'obs':             {'name': 'OBS Studio',        'category': 'communication',      'pricing': 'Free',                    'license': 'GPL 2.0',                   'website': 'https://obsproject.com',      'description': 'Free open-source software for video recording and live streaming.',      'github': 'obsproject/obs-studio',    'stars_approx': '57k'},
    'streamyard':      {'name': 'StreamYard',        'category': 'communication',      'pricing': 'Free / $25-$49/month',    'license': 'Proprietary',               'website': 'https://streamyard.com',      'description': 'Browser-based live streaming studio.',                  'founded': '2018', 'company': 'Hopin'},
    'wordpress-org':   {'name': 'WordPress.org',     'category': 'productivity',       'pricing': 'Free (self-hosted)',       'license': 'GPL 2.0',                   'website': 'https://wordpress.org',       'description': 'The world most popular CMS powering 43% of all websites.',        'github': 'WordPress/WordPress',      'stars_approx': '19k'},
    'wix':             {'name': 'Wix',               'category': 'productivity',       'pricing': 'Free / $17-$159/month',   'license': 'Proprietary',               'website': 'https://wix.com',             'description': 'Hosted website builder with drag-and-drop interface.',             'founded': '2006', 'company': 'Wix.com Ltd'},
    'squarespace':     {'name': 'Squarespace',       'category': 'productivity',       'pricing': '$16-$52/month',           'license': 'Proprietary',               'website': 'https://squarespace.com',     'description': 'All-in-one website builder known for beautiful templates.','founded': '2003', 'company': 'Squarespace Inc'},
    'webflow':         {'name': 'Webflow',           'category': 'design',             'pricing': 'Free / $14-$39/month',    'license': 'Proprietary',               'website': 'https://webflow.com',         'description': 'Visual web development platform combining design and CMS.',          'founded': '2013', 'company': 'Webflow Inc'},
    'ollama':          {'name': 'Ollama',            'category': 'developer-tools',    'pricing': 'Free',                    'license': 'MIT',                       'website': 'https://ollama.com',          'description': 'Run large language models locally on your own hardware.',       'github': 'ollama/ollama',            'stars_approx': '80k'},
    'openai-api':      {'name': 'OpenAI API',        'category': 'developer-tools',    'pricing': 'Pay per use ($0.01+/1k tokens)','license': 'Proprietary',          'website': 'https://openai.com',          'description': 'OpenAI API for accessing GPT-4, DALL-E, and Whisper models.',             'founded': '2015', 'company': 'OpenAI'},
}

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
    ('confluence',       'bookstack'),
    ('zendesk',          'zammad'),
    ('calendly',         'cal-com'),
    ('intercom',         'chatwoot'),
    ('postman',          'hoppscotch'),
    ('1password',        'bitwarden'),
    ('adobe-photoshop',  'gimp'),
    ('typeform',         'formbricks'),
    ('miro',             'excalidraw'),
    ('netlify',          'coolify'),
    ('salesforce',       'espocrm'),
    ('grammarly',        'languagetool'),
    ('shopify',          'woocommerce'),
    ('lastpass',         'vaultwarden'),
    ('quickbooks',       'akaunting'),
    ('docusign',         'docuseal'),
    ('sentry',           'glitchtip'),
    ('hotjar',           'openreplay'),
    ('loom',             'cap'),
    ('canva',            'penpot'),
    ('canva',            'inkscape'),
    ('sketch',           'penpot'),
    ('adobe-xd',         'penpot'),
    ('adobe-illustrator','inkscape'),
    ('adobe-premiere',   'kdenlive'),
    ('framer',           'plasmic'),
    ('figma',            'inkscape'),
    ('adobe-photoshop',  'penpot'),
    ('adobe-audition',   'audacity'),
    ('streamyard',       'obs'),
    ('wix',              'wordpress-org'),
    ('squarespace',      'wordpress-org'),
    ('webflow',          'plasmic'),
    ('openai-api',       'ollama'),
    ('adobe-premiere',   'kdenlive'),
    ('adobe-xd',         'penpot'),
    ('salesforce',       'vtiger'),
    ('zoho-crm',         'vtiger'),
    ('hubspot',          'espocrm'),
    ('quickbooks',       'dolibarr'),
    ('zoho-crm',         'dolibarr'),
    ('salesforce',       'dolibarr'),
]


def build_prompt(prop_key: str, oss_key: str) -> str:
    prop  = TOOLS.get(prop_key, {})
    alt   = TOOLS.get(oss_key,  {})
    year  = datetime.now().strftime('%Y')
    prop_name = prop.get('name', prop_key)
    oss_name  = alt.get('name', oss_key)
    return f"""You are a technical writer for a software comparison site. Generate a detailed Markdown comparison page.

Write the following sections in Markdown. Be objective, factual, and direct. Do not hedge.

# {prop_name} vs {oss_name} ({year})

## Overview
2-3 sentences: what both tools do and who benefits from this comparison.
Mention the core use case and the key reason someone would switch.

## Key Differences
Exactly 5 bullet points covering specific, named differences:
cost, data ownership, setup complexity, scalability, and one specific
feature or integration difference. Be concrete.

## Pricing Comparison
| Aspect | {prop_name} | {oss_name} |
|--------|----------|---------|
| Base Cost | {prop.get('pricing', 'N/A')} | {alt.get('pricing', 'Free')} |
| License | {prop.get('license', 'Proprietary')} | {alt.get('license', 'Open Source')} |
| Self-hosting | Not available | Available |
| Per-user cost at 50 users | Calculate approximate | $0 (server cost only) |
| Per-user cost at 200 users | Calculate approximate | $0 (server cost only) |

## Pros and Cons
Bullet lists of 4-5 pros and cons for each tool.
Include at least one honest limitation for {oss_name}.

## When to Choose Each
One paragraph per tool. Be specific about team type, size, and use case.

## Migration Path
3-5 numbered steps for migrating from {prop_name} to {oss_name}.
Include the actual export format and import tool where known.

---

After the main comparison, include these four additional sections:

## Our Take

Write 3 paragraphs (200-230 words total). Include in this order:
1. An honest production-readiness assessment of {oss_name} for most users right now
2. One specific technical limitation worth knowing before switching
3. A clear, direct recommendation: who should switch and who should not.

## Who Should Switch

Write a bulleted list of exactly 5 specific user types or scenarios
where switching from {prop_name} to {oss_name} clearly makes sense.
Each bullet must be specific about team size and which feature they do not need.

## FAQ

Generate 5 questions that someone searching "{oss_name} vs {prop_name}" would actually ask.
Answer each directly in 2-4 sentences. If the answer is no or not yet, say so.

Format:
### [Question here]
[Answer here]

## Meta

Output this JSON block at the very end. No markdown fences around it.

{{"meta_description": "140-160 character description starting with {oss_name}, mentioning free or self-hosted, ending with See full comparison or Free migration guide.", "publish_date_offset_days": INSERT_NUMBER_0_TO_240}}

For publish_date_offset_days choose a number between 0 and 240. Vary this for each page.

Return ONLY the Markdown content plus the Meta JSON. No preamble."""


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
            'max_tokens': 2500,
            'temperature': 0.6
        },
        timeout=30
    )
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content']


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


TEMPLATE_DETAILS = {
    ('slack', 'element'): {
        'overview': "Slack is the dominant workplace messaging platform, used by millions of teams worldwide for channel-based communication. Element is a decentralized, end-to-end encrypted alternative built on the open Matrix protocol, giving teams full control over their data and communications infrastructure.",
        'differences': ["**Cost**: Slack charges $7.25-$15/user/month; Element is free to self-host","**Data ownership**: Element runs on your own servers; Slack stores messages on Salesforce infrastructure","**Encryption**: Element provides end-to-end encryption by default; Slack encrypts in transit only","**Federation**: Element can communicate across Matrix servers; Slack is a closed silo","**Integrations**: Slack has 2,400+ app integrations; Element ecosystem is smaller but growing"],
        'when_prop': "Slack suits teams with large budgets that rely heavily on third-party integrations like Salesforce, Zoom, or Google Workspace.",
        'when_oss': "Element is ideal for security-conscious teams, organizations with strict data residency requirements, or teams eliminating per-seat SaaS costs.",
        'migration': "Export Slack message history via the data export tool, then start fresh in Element by recreating your channel structure. Mattermost also has a Slack import tool if you prefer that path."
    },
    ('slack', 'mattermost'): {
        'overview': "Slack is the leading proprietary team messaging platform offering rich integrations and a polished UI. Mattermost is an open-source alternative built for developer and DevOps teams, offering a familiar Slack-like experience with full self-hosting control.",
        'differences': ["**Cost**: Slack costs $7.25-$15/user/month; Mattermost self-hosted is free","**Deployment**: Mattermost can be deployed on your own servers or air-gapped environments","**DevOps integration**: Mattermost has deeper native CI/CD and DevOps workflow integration","**Data control**: All messages stay on your infrastructure with Mattermost","**Customization**: Mattermost open-source codebase can be modified; Slack cannot"],
        'when_prop': "Slack is best when your team prioritizes ease of onboarding and wants the widest third-party app ecosystem.",
        'when_oss': "Mattermost excels for engineering teams, regulated industries, or organizations needing air-gapped deployment.",
        'migration': "Mattermost provides an official Slack import script. Export your Slack workspace data, run the importer, and recreate integrations using Mattermost webhook and bot APIs."
    },
    ('notion', 'appflowy'): {
        'overview': "Notion is a popular all-in-one workspace combining notes, wikis, databases, and project management. AppFlowy is an open-source alternative with a local-first architecture that keeps your data on your device or own server.",
        'differences': ["**Cost**: Notion costs $8-$20/user/month; AppFlowy is completely free","**Data location**: AppFlowy stores data locally by default; Notion stores on their servers","**Offline support**: AppFlowy works fully offline; Notion requires internet for most features","**Privacy**: AppFlowy does not collect usage data; Notion privacy policy allows data analysis","**Feature parity**: Notion has more polished features and AI tools; AppFlowy is rapidly catching up"],
        'when_prop': "Notion suits teams wanting a polished workspace with AI writing tools and seamless collaboration without managing infrastructure.",
        'when_oss': "AppFlowy is ideal for privacy-conscious individuals, users in regions with data sovereignty requirements, or anyone needing offline-first functionality.",
        'migration': "Export your Notion workspace as Markdown plus CSV files, then import the Markdown files into AppFlowy. Database structures will need to be recreated manually."
    },
    ('github', 'gitlab'): {
        'overview': "GitHub is the world largest code hosting platform, owned by Microsoft, with 100 million developers. GitLab is a complete DevOps platform that can be fully self-hosted, offering everything from Git hosting to CI/CD and container registries.",
        'differences': ["**Cost**: GitHub free tier is generous; GitLab Community Edition is fully free to self-host","**CI/CD**: GitLab has more powerful built-in CI/CD pipelines; GitHub Actions is catching up","**Self-hosting**: GitLab is designed to be self-hosted; GitHub Enterprise self-hosted is expensive","**Feature scope**: GitLab is a complete DevSecOps platform; GitHub focuses on developer collaboration","**Community**: GitHub has a dramatically larger open-source community and project discoverability"],
        'when_prop': "GitHub suits open-source projects wanting maximum community visibility or teams deeply integrated with GitHub Actions workflows.",
        'when_oss': "GitLab self-hosted is ideal for enterprises needing full control over their DevOps stack or regulated industries.",
        'migration': "GitLab provides a GitHub importer that migrates repositories, issues, PRs, wikis, and milestones. Update CI configuration from GitHub Actions to GitLab CI/CD YAML format."
    },
    ('figma', 'penpot'): {
        'overview': "Figma is the dominant browser-based collaborative design tool used by most professional UI/UX teams. Penpot is an open-source alternative that also runs in the browser and uses open SVG-based file formats.",
        'differences': ["**Cost**: Figma charges $12-$75/user/month; Penpot is free to use or self-host","**File format**: Penpot uses open SVG-based formats; Figma uses proprietary binary formats","**Collaboration**: Both support real-time collaboration; Figma is more polished currently","**Plugin ecosystem**: Figma has thousands of plugins; Penpot library is smaller but growing","**Vendor risk**: Adobe acquisition attempt highlighted Figma vendor dependency risks"],
        'when_prop': "Figma suits professional design teams needing the most polished toolset and seamless handoff with tools like Zeplin or Storybook.",
        'when_oss': "Penpot is ideal for teams concerned about vendor lock-in, organizations with data privacy requirements, or budget-conscious teams.",
        'migration': "Export Figma designs as SVG files, which can be imported into Penpot. Complex components and auto-layout will require some manual recreation."
    },
    ('jira', 'plane'): {
        'overview': "Jira is the industry-standard issue and project tracking tool from Atlassian used for agile software development. Plane is a modern open-source alternative with a clean, fast interface.",
        'differences': ["**Cost**: Jira charges $7.75-$14.50/user/month; Plane is free to self-host","**Complexity**: Jira is notoriously complex and slow; Plane is designed to be fast","**Customization**: Jira has extensive workflow customization; Plane is simpler but improving","**Integrations**: Jira integrates with the entire Atlassian ecosystem; Plane offers REST API access","**Performance**: Plane modern architecture delivers significantly faster page loads"],
        'when_prop': "Jira suits large enterprises invested in the Atlassian ecosystem or teams needing highly customized workflow automation.",
        'when_oss': "Plane is ideal for startups and small-to-mid teams tired of Jira complexity.",
        'migration': "Export Jira issues as CSV, then import into Plane using the CSV importer. Custom fields and automations will need to be recreated."
    },
    ('trello', 'wekan'): {
        'overview': "Trello is a visual kanban board tool from Atlassian, simple and beginner-friendly. WeKan is an open-source kanban board offering the same card/list/board model without vendor dependency.",
        'differences': ["**Cost**: Trello paid plans start at $5/user/month; WeKan is completely free","**Data control**: WeKan runs on your own server; Trello data lives on Atlassian infrastructure","**Features**: Trello has a larger Power-Ups marketplace; WeKan covers core kanban features","**Setup**: Trello requires zero setup; WeKan requires a server","**Customization**: WeKan open-source code can be extended; Trello cannot"],
        'when_prop': "Trello suits individuals and small teams wanting instant zero-setup kanban with integrations to Slack, Google Drive, and GitHub.",
        'when_oss': "WeKan is ideal for teams wanting full data ownership or air-gapped deployments.",
        'migration': "Export Trello boards as JSON, then use WeKan Trello importer in Settings to recreate boards, lists, and cards."
    },
    ('dropbox', 'nextcloud'): {
        'overview': "Dropbox is one of the original cloud storage services offering simple file sync. Nextcloud is the most popular self-hosted cloud platform combining file storage, calendar, contacts, video calls, and 400+ apps.",
        'differences': ["**Cost**: Dropbox charges $9.99-$16.58/user/month; Nextcloud is free to self-host","**Storage**: Nextcloud storage is limited only by your server disk space","**Feature breadth**: Nextcloud is far more than storage; it is a full Google Workspace alternative","**Privacy**: Nextcloud on your own server means only you can access your data","**Setup**: Dropbox is instant; Nextcloud requires Docker setup"],
        'when_prop': "Dropbox suits individuals or small teams wanting simple reliable file sync with no infrastructure to manage.",
        'when_oss': "Nextcloud suits privacy-focused organizations wanting to eliminate cloud subscription costs.",
        'migration': "Download all Dropbox files locally, then upload to Nextcloud via the web interface or desktop sync client."
    },
    ('zoom', 'jitsi'): {
        'overview': "Zoom is the most widely used video conferencing platform. Jitsi Meet is a fully open-source alternative that runs in the browser with no account required and can be self-hosted for complete privacy.",
        'differences': ["**Cost**: Zoom free tier limits meetings to 40 minutes; Jitsi Meet is completely free","**Account**: Jitsi Meet requires no account for participants; Zoom requires account or app","**Privacy**: Self-hosted Jitsi is fully private; Zoom has had multiple privacy controversies","**Features**: Zoom has more enterprise features like webinars and AI tools; Jitsi covers core needs","**Self-hosting**: Jitsi deploys on a small VPS in minutes; Zoom cannot be self-hosted"],
        'when_prop': "Zoom suits large organizations needing webinar features, enterprise phone systems, and HIPAA compliance.",
        'when_oss': "Jitsi is ideal for small teams, privacy-conscious users, or anyone wanting quick meetings without requiring participants to install software.",
        'migration': "No migration needed. Share a Jitsi meeting link instead of a Zoom link. Replace Zoom calendar links with Jitsi room URLs."
    },
    ('salesforce', 'vtiger'): {
        'overview': "Salesforce is the world's leading CRM platform, used by enterprises globally for sales automation, customer service, and analytics. Vtiger CRM is a mature open-source alternative with a full-featured community edition covering contacts, leads, sales pipelines, and support ticketing — self-hosted at zero license cost.",
        'differences': [
            "**Cost**: Salesforce charges $25-$300+/user/month; Vtiger Community Edition is completely free to self-host",
            "**Complexity**: Salesforce requires dedicated admins and often consultants; Vtiger is manageable by a small ops team",
            "**Data ownership**: Vtiger self-hosted keeps all customer data on your own infrastructure",
            "**Customization**: Both support custom fields and modules; Vtiger source code can be modified directly",
            "**Ecosystem**: Salesforce AppExchange has thousands of add-ons; Vtiger has a smaller but growing extension library"
        ],
        'when_prop': "Salesforce suits large enterprises needing deep AI-driven analytics, complex multi-cloud integrations, and dedicated Salesforce admin teams to manage the platform.",
        'when_oss': "Vtiger is ideal for SMBs and startups that need a full CRM without the $25-$300/user/month cost, especially teams comfortable running a VPS.",
        'migration': "Export Salesforce records as CSV from the Data Export Service, then import contacts, leads, accounts, and opportunities into Vtiger using its built-in CSV importer. Map Salesforce custom fields to Vtiger equivalents before importing. Run both systems in parallel for 2-4 weeks before cutover."
    },
    ('zoho-crm', 'vtiger'): {
        'overview': "Zoho CRM is a popular mid-market CRM platform offering sales automation, email marketing, and AI-powered insights at a lower price point than Salesforce. Vtiger CRM is a free open-source alternative that shares DNA with early Zoho and SugarCRM builds, making it a natural migration target for Zoho users wanting to eliminate per-seat costs.",
        'differences': [
            "**Cost**: Zoho CRM charges $14-$52/user/month; Vtiger Community Edition is free to self-host",
            "**Hosting**: Vtiger runs on your own server; Zoho is cloud-only with no self-hosted option",
            "**Data privacy**: Vtiger keeps all CRM data on infrastructure you control; Zoho stores data on their servers",
            "**Feature parity**: Zoho has more built-in marketing automation; Vtiger covers core CRM needs well",
            "**Vendor risk**: Vtiger eliminates dependency on Zoho pricing changes or account suspension"
        ],
        'when_prop': "Zoho CRM suits teams wanting a polished cloud CRM with tight integration into the broader Zoho suite including Books, Campaigns, and Desk.",
        'when_oss': "Vtiger is the right move for SMBs paying Zoho per-seat fees who primarily use contacts, pipelines, and basic reporting — and have at least one technical person on the team.",
        'migration': "Export Zoho CRM data via Settings → Data Administration → Export. Download CSVs for Contacts, Leads, Accounts, and Deals. Use Vtiger's CSV import tool to bring in each module. Recreate any Zoho workflow automations manually as Vtiger workflows."
    },
    ('hubspot', 'espocrm'): {
        'overview': "HubSpot is an all-in-one CRM, marketing, and sales platform with a generous free tier that scales into expensive paid plans. EspoCRM is a clean, lightweight open-source CRM covering contacts, leads, accounts, opportunities, and reporting — entirely free to self-host with no feature gating.",
        'differences': [
            "**Cost**: HubSpot free tier is limited; paid plans run $15-$800+/month — EspoCRM self-hosted is always free",
            "**Feature gating**: HubSpot locks key features behind higher tiers; EspoCRM gives full access from day one",
            "**Data ownership**: EspoCRM on your server means your CRM data never leaves your infrastructure",
            "**UI simplicity**: EspoCRM has a cleaner, faster interface than HubSpot's increasingly complex dashboard",
            "**Marketing tools**: HubSpot has superior built-in email marketing automation; EspoCRM focuses on core CRM"
        ],
        'when_prop': "HubSpot suits marketing-led teams that need tight CRM and email campaign integration, landing pages, and lead scoring in a single managed platform.",
        'when_oss': "EspoCRM is ideal for sales-focused teams that hit HubSpot's free tier limits or are facing $400+/month Professional plan costs and primarily need pipeline and contact management.",
        'migration': "Export HubSpot contacts, companies, and deals as CSV via Settings → Data Management → Export. Import into EspoCRM using the built-in import wizard under Admin → Import. Map HubSpot deal stages to EspoCRM opportunity stages before importing. Note that HubSpot email sequences and workflows will need to be rebuilt manually."
    },
    ('quickbooks', 'dolibarr'): {
        'overview': "QuickBooks is the dominant small business accounting platform from Intuit, used by millions of businesses for invoicing, payroll, and tax preparation. Dolibarr is a free open-source ERP and CRM that covers accounting, invoicing, stock management, and customer tracking — replacing both QuickBooks and a basic CRM in a single self-hosted install.",
        'differences': [
            "**Cost**: QuickBooks charges $30-$200+/month; Dolibarr is completely free to self-host",
            "**Scope**: Dolibarr combines ERP, CRM, and accounting in one tool; QuickBooks is accounting-focused",
            "**Data ownership**: Dolibarr self-hosted keeps all financial records on your own server",
            "**Accountant access**: QuickBooks has native accountant collaboration features; Dolibarr requires sharing server access",
            "**Tax compliance**: QuickBooks has built-in US tax filing integrations; Dolibarr requires manual tax configuration"
        ],
        'when_prop': "QuickBooks suits US-based small businesses needing seamless payroll processing, tax preparation, and direct accountant collaboration with minimal setup.",
        'when_oss': "Dolibarr is ideal for small businesses outside the US, freelancers, or teams wanting to eliminate monthly SaaS fees and manage CRM and accounting in one self-hosted platform.",
        'migration': "Export QuickBooks data via Reports → Export to Excel for your chart of accounts, customer list, and transaction history. Dolibarr supports CSV import for contacts and products. Financial history will need manual entry or accounting journal imports — plan for a clean start-of-year cutover to simplify the transition."
    },
    ('zoho-crm', 'dolibarr'): {
        'overview': "Zoho CRM is a cloud-based sales and marketing platform popular with SMBs for its balance of features and price. Dolibarr is an open-source ERP and CRM that goes further — covering not just customer management but also invoicing, stock, and accounting — making it a compelling alternative for businesses wanting a single self-hosted system to replace multiple Zoho subscriptions.",
        'differences': [
            "**Cost**: Zoho CRM charges $14-$52/user/month plus additional Zoho apps; Dolibarr is free to self-host",
            "**Scope**: Dolibarr is a full ERP replacing CRM, invoicing, and inventory tools; Zoho CRM is CRM-only",
            "**Data control**: Dolibarr on your server means complete data sovereignty; Zoho is cloud-only",
            "**Module breadth**: Dolibarr covers HR, projects, POS, and manufacturing modules; Zoho CRM requires separate paid apps",
            "**UI modernity**: Zoho CRM has a more polished modern interface; Dolibarr's UI is functional but dated"
        ],
        'when_prop': "Zoho CRM suits teams already using the Zoho ecosystem who value tight integration between CRM, email, and support tools without managing any infrastructure.",
        'when_oss': "Dolibarr is the right fit for small businesses paying for multiple Zoho apps who want to consolidate into one free self-hosted platform — especially outside the US where Zoho's pricing hits harder.",
        'migration': "Export Zoho CRM contacts, accounts, and deals as CSV. Import into Dolibarr's Third Parties and Opportunities modules using the CSV import tool. For Zoho Books users, export invoices and products separately and import into Dolibarr's billing and product catalog modules."
    },
    ('salesforce', 'dolibarr'): {
        'overview': "Salesforce is the enterprise CRM standard, powerful but expensive and complex. Dolibarr is a free open-source ERP and CRM built for SMBs, covering customer management, invoicing, stock, and projects in one self-hosted package — at a fraction of the operational cost.",
        'differences': [
            "**Cost**: Salesforce costs $25-$300+/user/month; Dolibarr is free with server costs under $15/month",
            "**Target scale**: Salesforce is built for large enterprises; Dolibarr is optimized for SMBs under 100 users",
            "**ERP scope**: Dolibarr combines CRM with accounting and inventory; Salesforce requires expensive add-ons for that",
            "**Implementation**: Salesforce typically needs a consultant to implement; Dolibarr can be set up by a non-specialist",
            "**Data ownership**: Dolibarr self-hosted gives you full control; Salesforce data lives on their infrastructure"
        ],
        'when_prop': "Salesforce suits enterprises with dedicated CRM admin teams, complex multi-territory sales operations, and budgets that justify $1,000-$10,000+/month in licenses.",
        'when_oss': "Dolibarr is ideal for SMBs that were pushed toward Salesforce by a consultant but actually only need basic pipeline tracking, invoicing, and contact management.",
        'migration': "Use Salesforce Data Export Service to download CSVs of Accounts, Contacts, Opportunities, and Tasks. Import Accounts and Contacts into Dolibarr's Third Parties module, and Opportunities into the Projects or CRM Opportunities module. Recreate key Salesforce reports manually as Dolibarr report templates."
    },
}


def generate_with_template(prop_key: str, oss_key: str) -> str:
    prop     = TOOLS.get(prop_key, {})
    alt      = TOOLS.get(oss_key,  {})
    month    = datetime.now().strftime('%B %Y')
    pair_key = (prop_key, oss_key)
    details  = TEMPLATE_DETAILS.get(pair_key)

    prop_name = prop.get('name', prop_key)
    oss_name  = alt.get('name', oss_key)

    if details:
        overview     = details['overview']
        diff_bullets = '\n'.join(f'- {d}' for d in details['differences'])
        when_prop    = details['when_prop']
        when_oss     = details['when_oss']
        migration    = details['migration']
    else:
        overview     = (f"{prop.get('description', prop_name)} is a popular proprietary tool in the "
                        f"{prop.get('category', 'software')} space. {oss_name} is a free, open-source "
                        f"alternative that gives organizations complete control over their data and deployment.")
        diff_bullets = (f"- **Cost**: {prop_name} costs {prop.get('pricing', 'see website')}; {oss_name} is {alt.get('pricing', 'free')}\n"
                        f"- **License**: {prop_name} is {prop.get('license', 'proprietary')}; {oss_name} is {alt.get('license', 'open source')}\n"
                        f"- **Data ownership**: {oss_name} can be self-hosted so your data stays on infrastructure you control\n"
                        f"- **Vendor lock-in**: {oss_name} eliminates dependency on a single commercial vendor\n"
                        f"- **Community**: {oss_name} has an active open-source community contributing features and fixes")
        when_prop    = (f"{prop_name} is the right choice when you need the most polished user experience, "
                        f"the broadest integration ecosystem, and professional support with SLA guarantees.")
        when_oss     = (f"{oss_name} is ideal for privacy-conscious teams, organizations with strict data "
                        f"sovereignty requirements, or anyone wanting to eliminate per-seat subscription costs.")
        migration    = (f"Export your data from {prop_name} in its standard export format, review "
                        f"{oss_name} import documentation, and plan a pilot period where both tools run in parallel.")

    try:
        price_raw      = prop.get('pricing', '$0')
        price_per_user = float(''.join(c for c in price_raw.split('-')[0].split('/')[0] if c.isdigit() or c == '.'))
        cost_50        = f"~${price_per_user * 50:,.0f}/month"
        cost_200       = f"~${price_per_user * 200:,.0f}/month"
    except Exception:
        cost_50  = "See pricing page"
        cost_200 = "See pricing page"

    github_badge = (f"\n> GitHub: [{alt.get('github','')}](https://github.com/{alt.get('github','')}) "
                    f"* ~{alt.get('stars_approx','N/A')} stars" if alt.get('github') else "")

    offset    = random.randint(0, 240)
    meta_desc = f"{oss_name} is a free, self-hosted alternative to {prop_name}. Compare pricing, features, and migration steps. See full comparison."
    if len(meta_desc) > 160:
        meta_desc = meta_desc[:157] + "..."

    return f"""# {prop_name} vs {oss_name}

## Overview

{overview}

## Key Differences

{diff_bullets}

## Pricing Comparison

| Aspect | {prop_name} | {oss_name} |
|--------|-------------------------------|-------------------------------|
| Base pricing | {prop.get('pricing', 'N/A')} | {alt.get('pricing', 'Free')} |
| License | {prop.get('license', 'Proprietary')} | {alt.get('license', 'Open Source')} |
| Self-hosting | Not available | Available |
| Cost at 50 users | {cost_50} | $0/month (self-hosted) |
| Cost at 200 users | {cost_200} | $0/month (self-hosted) |
| Vendor lock-in | High | None |

## Pros and Cons

### {prop_name}

**Pros:**
- Polished, professionally designed user interface
- Large ecosystem of official integrations
- Managed infrastructure with no server maintenance required
- Enterprise SLA and dedicated support available
- Mobile apps are well-maintained and reliable

**Cons:**
- Significant per-user monthly cost that scales linearly with team size
- Your data is stored on the vendor infrastructure
- No ability to inspect or modify the source code
- Feature roadmap controlled entirely by the vendor
- Risk of pricing changes, acquisition, or discontinuation

### {oss_name}

**Pros:**
- Free to self-host with costs only for server infrastructure
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

**Choose {prop_name} if:** {when_prop}

**Choose {oss_name} if:** {when_oss}

## Migration Path

{migration}

## Our Take

{oss_name} is production-ready for most teams willing to invest a few hours in setup. The self-hosted version gives you identical or better functionality to the paid {prop_name} tiers, with no recurring per-seat cost.

The main technical limitation worth knowing: you are responsible for your own backups, updates, and uptime. If your server goes down, so does your {oss_name} instance. Plan for this with automated backups and a monitoring alert.

Our recommendation: if your team has at least one developer and you are paying more than $100/month for {prop_name}, switching to self-hosted {oss_name} will pay for itself within the first month. If nobody on your team is comfortable with Linux or Docker, stay on {prop_name} until you have that resource.

## Who Should Switch

- Startups under 20 people paying per-seat fees they cannot yet justify
- Dev teams who already self-host other tools and have the ops knowledge
- Organizations in jurisdictions with strict data residency requirements
- Teams who have evaluated {prop_name} paid features and only use the basics
- Founders and solopreneurs who want the functionality without the subscription

## FAQ

### Is {oss_name} free to use?
Yes. {oss_name} is free to self-host. Your only cost is the server, typically $6-$12/month on a VPS provider like DigitalOcean or Vultr.

### How hard is it to migrate from {prop_name} to {oss_name}?
For most teams, migration takes 2-4 hours. Export your {prop_name} data, follow the {oss_name} import guide, and test with a small group before switching everyone over.

### Does {oss_name} get regular updates?
Yes. {oss_name} has an active open-source community with regular releases. Check the GitHub repository for release frequency.

### Can I use {oss_name} without technical knowledge?
You need basic comfort with a VPS and command line. If that feels unfamiliar, there are managed hosting options that handle the server for you at a modest cost.

### What happens if {oss_name} development stops?
Because the source code is open, you can continue running whatever version you have indefinitely. You can also fork the project or switch to another tool at your own pace — no vendor can shut off your instance.

---
*Data sourced {month}. Pricing and features change. Verify at [{prop_name}]({prop.get('website', '')}) and [{oss_name}]({alt.get('website', '')}) before making decisions.*

## Meta
{{"meta_description": "{meta_desc}", "publish_date_offset_days": {offset}}}"""


def extract_meta(response_text: str) -> dict:
    patterns = [
        r'\{[^{}]*"meta_description"[^{}]*"publish_date_offset_days"[^{}]*\}',
        r'\{[^{}]*"publish_date_offset_days"[^{}]*"meta_description"[^{}]*\}',
    ]
    for pattern in patterns:
        matches = list(re.finditer(pattern, response_text, re.DOTALL))
        if matches:
            try:
                raw = matches[-1].group()
                raw = re.sub(r'[\x00-\x1f\x7f]', ' ', raw)
                return json.loads(raw)
            except Exception:
                pass
    return {"meta_description": "", "publish_date_offset_days": random.randint(0, 240)}


def offset_to_date(offset_days: int) -> str:
    jitter   = timedelta(days=random.randint(-2, 2))
    pub_date = datetime.utcnow() - timedelta(days=int(offset_days)) + jitter
    return pub_date.strftime("%B %d, %Y")


def strip_meta_block(content: str) -> str:
    cleaned = re.sub(r'\n*##\s*Meta\s*\n[\s\S]*', '', content, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'\n*\{[^{}]*"meta_description"[^{}]*\}\s*$', '', cleaned, flags=re.DOTALL).strip()
    return cleaned


def generate_comparison(prop_key: str, oss_key: str) -> Dict:
    prompt        = build_prompt(prop_key, oss_key)
    prop          = TOOLS.get(prop_key, {})
    alt           = TOOLS.get(oss_key,  {})
    content       = None
    provider_used = None

    try:
        content = generate_with_groq(prompt)
        provider_used = 'groq'
        logger.info(f"    Generated with Groq")
    except Exception as e:
        logger.warning(f"    Groq unavailable ({type(e).__name__}) -- trying Gemini...")
        time.sleep(2)

    if content is None:
        try:
            content = generate_with_gemini(prompt)
            provider_used = 'gemini'
            logger.info(f"    Generated with Gemini")
        except Exception as e:
            logger.warning(f"    Gemini unavailable ({type(e).__name__}) -- using template...")

    if content is None:
        content = generate_with_template(prop_key, oss_key)
        provider_used = 'template'
        logger.info(f"    Generated with template engine")

    meta             = extract_meta(content)
    meta_description = meta.get('meta_description', '')
    offset_days      = meta.get('publish_date_offset_days', random.randint(0, 240))
    publish_date     = offset_to_date(offset_days)
    clean_content    = strip_meta_block(content)

    return {
        'id':                  f'{prop_key}-vs-{oss_key}',
        'slug':                f'{prop_key}-vs-{oss_key}',
        'title':               f"{prop.get('name', prop_key)} vs {alt.get('name', oss_key)}",
        'proprietary_tool':    prop.get('name', prop_key),
        'proprietary_key':     prop_key,
        'oss_tool':            alt.get('name', oss_key),
        'oss_key':             oss_key,
        'category':            alt.get('category', 'general'),
        'proprietary_pricing': prop.get('pricing', 'N/A'),
        'oss_pricing':         alt.get('pricing', 'Free'),
        'proprietary_website': prop.get('website', ''),
        'oss_website':         alt.get('website', ''),
        'oss_github':          alt.get('github', ''),
        'oss_stars':           alt.get('stars_approx', ''),
        'comparison_markdown': clean_content,
        'meta_description':    meta_description,
        'publish_date':        publish_date,
        'provider':            provider_used,
        'generated_at':        datetime.utcnow().isoformat() + 'Z',
        'status':              'generated'
    }


def main():
    parser = argparse.ArgumentParser(description='Generate AI comparisons')
    parser.add_argument('--index',   '-i', type=int, default=1)
    parser.add_argument('--output',  '-o', default='.cache/publish')
    parser.add_argument('--dlq-dir', '-d', default='./dlq')
    args = parser.parse_args()

    Path(args.output).mkdir(parents=True, exist_ok=True)
    dlq   = DeadLetterQueue(args.dlq_dir)
    start = (args.index - 1) * 10
    batch = COMPARISON_PAIRS[start:start + 10]

    if not batch:
        max_batch = (len(COMPARISON_PAIRS) // 10) + 1
        logger.warning(f"No comparisons in batch {args.index}. Max index: {max_batch}")
        return

    logger.info(f"Generating batch {args.index}: {len(batch)} comparisons...")
    generated, failed = [], []

    for prop_key, oss_key in batch:
        prop_name = TOOLS.get(prop_key, {}).get('name', prop_key)
        oss_name  = TOOLS.get(oss_key,  {}).get('name', oss_key)
        logger.info(f"  {prop_name} vs {oss_name}")
        try:
            result = generate_comparison(prop_key, oss_key)
            generated.append(result)
            time.sleep(2)
        except Exception as e:
            logger.error(f"  Failed: {prop_key} vs {oss_key}: {e}")
            failed.append({'proprietary': prop_key, 'oss': oss_key, 'error': str(e)})
            dlq.save_failed({'type': 'comparison', 'proprietary': prop_key, 'oss': oss_key}, e)

    if generated:
        out_path = Path(args.output) / f'comparisons_{args.index}.json'
        with open(out_path, 'w') as f:
            json.dump(generated, f, indent=2)
        logger.info(f"  Saved {len(generated)} comparisons to {out_path}")

    logger.info(f"  Generated: {len(generated)}  |  Failed: {len(failed)}")
    if failed:
        send_slack_alert(f"Warning: {len(failed)} comparisons failed in batch {args.index}", "warning")


if __name__ == "__main__":
    main()
