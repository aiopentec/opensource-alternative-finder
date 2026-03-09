#!/usr/bin/env python3
"""
scrape_sources.py — Fetch open-source project data from GitHub and Reddit.
Usage: python scripts/scrape_sources.py --source github --tools slack,notion
"""

import argparse, json, logging, os, sys, time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import requests

sys.path.insert(0, str(Path(__file__).parent))
from utils_resilience import resilient_request, CircuitBreaker

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)

github_cb = CircuitBreaker('github', failure_threshold=3)
reddit_cb = CircuitBreaker('reddit', failure_threshold=5)


@resilient_request(max_retries=3)
def github_request(endpoint: str, params: Optional[Dict] = None) -> Dict:
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    url = f"https://api.github.com{endpoint}"
    resp = requests.get(url, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


@resilient_request(max_retries=3)
def reddit_request(endpoint: str, params: Optional[Dict] = None) -> Dict:
    url = f"https://www.reddit.com{endpoint}"
    headers = {"User-Agent": "OpenSourceFinder/1.0 (automated research tool)"}
    resp = requests.get(url, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_github_data(tools: Optional[List[str]] = None) -> List[Dict]:
    logger.info("🔍 Scraping GitHub...")
    results = []
    default_tools = ['slack', 'notion', 'github', 'figma', 'jira', 'trello', 'dropbox', 'zoom']
    search_tools = tools or default_tools

    for tool in search_tools[:8]:
        try:
            data = github_cb.call(
                github_request,
                '/search/repositories',
                params={'q': f'{tool} open source alternative', 'sort': 'stars', 'order': 'desc', 'per_page': 5}
            )
            for repo in data.get('items', [])[:3]:
                results.append({
                    'source': 'github',
                    'search_query': tool,
                    'id': f"{repo['owner']['login']}/{repo['name']}",
                    'name': repo['name'],
                    'full_name': repo['full_name'],
                    'description': repo.get('description', ''),
                    'stars': repo.get('stargazers_count', 0),
                    'forks': repo.get('forks_count', 0),
                    'language': repo.get('language'),
                    'license': repo.get('license', {}).get('spdx_id') if repo.get('license') else None,
                    'url': repo['html_url'],
                    'topics': repo.get('topics', []),
                    'fetched_at': datetime.utcnow().isoformat() + 'Z'
                })
            time.sleep(1.0)
        except Exception as e:
            logger.error(f"GitHub search failed for '{tool}': {e}")

    logger.info(f"✅ Scraped {len(results)} GitHub repositories")
    return results


def fetch_reddit_data(tools: Optional[List[str]] = None) -> List[Dict]:
    logger.info("🔍 Scraping Reddit...")
    results = []
    subreddits = ['opensource', 'selfhosted', 'privacy', 'devops']

    for subreddit in subreddits[:4]:
        try:
            data = reddit_cb.call(
                reddit_request,
                f'/r/{subreddit}/hot.json',
                params={'limit': 20}
            )
            for post in data.get('data', {}).get('children', [])[:5]:
                pd = post.get('data', {})
                results.append({
                    'source': 'reddit',
                    'id': pd.get('id'),
                    'subreddit': subreddit,
                    'title': pd.get('title'),
                    'score': pd.get('score', 0),
                    'url': f"https://reddit.com{pd.get('permalink', '')}",
                    'fetched_at': datetime.utcnow().isoformat() + 'Z'
                })
            time.sleep(2.0)
        except Exception as e:
            logger.error(f"Reddit fetch failed for r/{subreddit}: {e}")

    logger.info(f"✅ Scraped {len(results)} Reddit posts")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', '-s', required=True, choices=['github', 'reddit', 'all'])
    parser.add_argument('--output', '-o', default='.cache/scrape')
    parser.add_argument('--tools', '-t', default='')
    args = parser.parse_args()

    tools = [t.strip() for t in args.tools.split(',')] if args.tools else None
    Path(args.output).mkdir(parents=True, exist_ok=True)

    if args.source in ['github', 'all']:
        data = fetch_github_data(tools)
        with open(f'{args.output}/github.jsonl', 'w') as f:
            for item in data:
                f.write(json.dumps(item) + '\n')
        logger.info(f"💾 Saved {len(data)} GitHub items")

    if args.source in ['reddit', 'all']:
        data = fetch_reddit_data(tools)
        with open(f'{args.output}/reddit.jsonl', 'w') as f:
            for item in data:
                f.write(json.dumps(item) + '\n')
        logger.info(f"💾 Saved {len(data)} Reddit items")

    logger.info("✅ Scraping complete!")


if __name__ == "__main__":
    main()
