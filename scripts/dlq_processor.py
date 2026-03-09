#!/usr/bin/env python3
"""
dlq_processor.py — Retry items that failed in previous pipeline runs.
Usage: python scripts/dlq_processor.py
"""

import argparse, json, logging, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils_resilience import DeadLetterQueue, send_slack_alert

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Process dead letter queue')
    parser.add_argument('--dlq-dir', '-d', default='./dlq')
    parser.add_argument('--max-retries', '-m', type=int, default=3)
    args = parser.parse_args()

    dlq = DeadLetterQueue(args.dlq_dir)
    stats = dlq.get_stats()
    logger.info(f'📬 DLQ Stats: {stats}')

    failed_items = dlq.list_items('failed')
    if not failed_items:
        logger.info('✅ DLQ is clean — no failed items to process')
        return

    logger.info(f'🔄 Processing {len(failed_items)} failed items...')
    retried = 0
    moved_to_dead = 0

    for filepath, data in failed_items:
        retry_count = data.get('retry_count', 0)
        task_data   = data.get('task_data', {})
        task_type   = task_data.get('type', 'unknown')

        if retry_count >= args.max_retries:
            new_path = Path(args.dlq_dir) / 'dead' / filepath.name
            filepath.rename(new_path)
            moved_to_dead += 1
            logger.warning(f'💀 → dead: {filepath.name} (exhausted {retry_count} retries)')
        else:
            data['retry_count'] = retry_count + 1
            data['last_retry_attempt'] = datetime.utcnow().isoformat() + 'Z'
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            retried += 1
            logger.info(f'♻️  Queued: {task_type} (attempt {retry_count + 1}/{args.max_retries})')

    logger.info('=' * 50)
    logger.info(f'Queued for retry: {retried}  |  Permanently failed: {moved_to_dead}')
    logger.info(f'Final DLQ: {dlq.get_stats()}')

    if moved_to_dead > 0:
        send_slack_alert(f'📬 DLQ: {moved_to_dead} items permanently failed — review dlq/dead/', 'warning')


if __name__ == "__main__":
    main()
