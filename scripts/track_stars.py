#!/usr/bin/env python3
"""
track_stars.py
Reads current comparison data, updates star_history.json,
and outputs momentum scores (week-over-week star deltas).

Run after generate step, before publish step.
Commits star_history.json back to repo so history accumulates over time.

Usage: python scripts/track_stars.py --cache .cache/publish --history data/star_history.json
"""

import json
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)


def load_comparisons(cache_dir: str) -> List[Dict]:
    comparisons = []
    for json_file in sorted(Path(cache_dir).glob('comparisons_*.json')):
        with open(json_file) as f:
            comparisons.extend(json.load(f))
    return comparisons


def parse_stars(stars_str: str) -> int:
    """Convert '30k', '1.2k', '90k', '123' to integer."""
    if not stars_str:
        return 0
    s = str(stars_str).strip().lower().replace(',', '')
    try:
        if s.endswith('k'):
            return int(float(s[:-1]) * 1000)
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def compute_momentum(history: Dict, today_str: str) -> List[Dict]:
    """
    For each tool compute star delta vs 7 days ago.
    Returns list sorted by delta descending.
    """
    results = []
    week_ago = (datetime.strptime(today_str, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')

    for tool_key, snapshots in history.items():
        if len(snapshots) < 2:
            continue
        # Get today's count and the oldest count within last 7 days
        today_entry = snapshots[-1]
        # Find entry closest to 7 days ago
        past_entry = None
        for snap in reversed(snapshots[:-1]):
            if snap['date'] <= week_ago:
                past_entry = snap
                break
        if not past_entry:
            past_entry = snapshots[0]

        today_stars = today_entry['stars']
        past_stars  = past_entry['stars']
        delta       = today_stars - past_stars
        days_apart  = max(1, (datetime.strptime(today_entry['date'], '%Y-%m-%d') -
                              datetime.strptime(past_entry['date'], '%Y-%m-%d')).days)
        weekly_rate = int(delta / days_apart * 7)

        if delta > 0:
            results.append({
                'oss_key':    tool_key,
                'oss_name':   today_entry['name'],
                'oss_github': today_entry.get('github', ''),
                'stars_now':  today_stars,
                'stars_then': past_stars,
                'delta':      delta,
                'weekly_rate': weekly_rate,
                'days_measured': days_apart,
                'slug':       today_entry.get('slug', ''),
                'prop_name':  today_entry.get('prop_name', ''),
            })

    results.sort(key=lambda x: x['weekly_rate'], reverse=True)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache',   default='.cache/publish')
    parser.add_argument('--history', default='data/star_history.json')
    parser.add_argument('--output',  default='.cache/publish/momentum.json')
    args = parser.parse_args()

    today = datetime.utcnow().strftime('%Y-%m-%d')

    # Load existing history
    history_path = Path(args.history)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    if history_path.exists():
        with open(history_path) as f:
            history = json.load(f)
    else:
        history = {}
        logger.info("No existing star history found — starting fresh")

    # Load current comparisons and update history
    comparisons = load_comparisons(args.cache)
    if not comparisons:
        logger.warning("No comparisons found in cache")
        return

    updated = 0
    for comp in comparisons:
        oss_key   = comp.get('oss_key', '')
        oss_name  = comp.get('oss_tool', '')
        oss_github = comp.get('oss_github', '')
        stars_str = comp.get('oss_stars', '')
        stars     = parse_stars(stars_str)
        slug      = comp.get('slug', '')
        prop_name = comp.get('proprietary_tool', '')

        if not oss_key or stars == 0:
            continue

        if oss_key not in history:
            history[oss_key] = []

        # Only add one snapshot per day
        existing_dates = [s['date'] for s in history[oss_key]]
        if today not in existing_dates:
            history[oss_key].append({
                'date':   today,
                'stars':  stars,
                'name':   oss_name,
                'github': oss_github,
                'slug':   slug,
                'prop_name': prop_name,
            })
            updated += 1

        # Keep only last 90 days of history to avoid unbounded growth
        history[oss_key] = [
            s for s in history[oss_key]
            if s['date'] >= (datetime.utcnow() - timedelta(days=90)).strftime('%Y-%m-%d')
        ]

    logger.info(f"Updated {updated} tool snapshots for {today}")

    # Save updated history
    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2)
    logger.info(f"Saved star history to {history_path} ({len(history)} tools tracked)")

    # Compute momentum
    momentum = compute_momentum(history, today)
    logger.info(f"Computed momentum for {len(momentum)} tools with positive growth")

    # Save momentum output for publish script
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(momentum[:20], f, indent=2)  # Top 20
    logger.info(f"Saved top {min(20, len(momentum))} trending tools to {args.output}")

    # Print top 5 for pipeline logs
    for i, m in enumerate(momentum[:5], 1):
        logger.info(f"  #{i} {m['oss_name']}: +{m['weekly_rate']:,} stars/week "
                    f"({m['stars_then']:,} → {m['stars_now']:,})")


if __name__ == '__main__':
    main()
