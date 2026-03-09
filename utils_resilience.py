#!/usr/bin/env python3
"""
utils_resilience.py — Safety system: retries, circuit breakers, dead-letter queue, alerts.
"""

import json, logging, os, random, time
from datetime import datetime
from pathlib import Path
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)


def resilient_request(max_retries: int = 3, base_delay: float = 1.0):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            import requests
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_retries - 1:
                        logger.error(f"❌ {func.__name__} failed after {max_retries} attempts")
                        raise
                    delay = min(base_delay * (2 ** attempt), 30)
                    jitter = random.uniform(0, 0.5)
                    logger.warning(f"⚠️  Retry {attempt+1}/{max_retries} in {delay+jitter:.1f}s")
                    time.sleep(delay + jitter)
            raise last_exception
        return wrapper
    return decorator


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: int = 300):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure: Optional[datetime] = None
        self.state = "CLOSED"

    def call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == "OPEN":
            elapsed = (datetime.now() - self.last_failure).total_seconds()
            if elapsed > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info(f"🔄 {self.name}: Testing recovery...")
            else:
                raise RuntimeError(f"🛑 {self.name} circuit is OPEN — skipping")
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise

    def _on_success(self):
        self.state = "CLOSED"
        self.failures = max(0, self.failures - 1)
        logger.info(f"✅ {self.name}: OK")

    def _on_failure(self, exc: Exception):
        self.failures += 1
        self.last_failure = datetime.now()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.error(f"🛑 {self.name} circuit TRIPPED after {self.failures} failures")


class DeadLetterQueue:
    def __init__(self, base_dir: str = "./dlq"):
        self.base_dir = Path(base_dir)
        for subdir in ["failed", "dead", "success"]:
            (self.base_dir / subdir).mkdir(parents=True, exist_ok=True)
        logger.info(f"📬 DLQ ready at {self.base_dir}")

    def save_failed(self, task_data: Dict, error: Exception, context: Optional[Dict] = None):
        retry_count = task_data.get("retry_count", 0) + 1
        task_id = task_data.get("id") or task_data.get("slug") or str(abs(hash(str(task_data))))[:8]
        payload = {
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "retry_count": retry_count,
            "error": {"type": type(error).__name__, "message": str(error)},
            "context": context or {},
            "task_data": task_data
        }
        target = "dead" if retry_count > 3 else "failed"
        filename = f"{int(time.time())}_{task_id}_{retry_count}.json"
        filepath = self.base_dir / target / filename
        with open(filepath, 'w') as f:
            json.dump(payload, f, indent=2)
        status = "💀 PERMANENT" if target == "dead" else "⚠️  QUEUED FOR RETRY"
        logger.error(f"{status}: {filename}")

    def list_items(self, status: str = 'failed') -> List[Tuple[Path, Dict]]:
        items = []
        for f in (self.base_dir / status).glob('*.json'):
            try:
                with open(f) as fp:
                    items.append((f, json.load(fp)))
            except Exception as e:
                logger.warning(f"Corrupt DLQ file {f}: {e}")
        return sorted(items, key=lambda x: x[0].name)

    def get_stats(self) -> Dict[str, int]:
        return {s: len(list((self.base_dir / s).glob("*.json"))) for s in ["failed", "dead", "success"]}


def send_slack_alert(message: str, severity: str = 'warning'):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return
    colors = {"critical": "#ff0000", "warning": "#ff9900", "info": "#3366cc"}
    payload = {"attachments": [{"color": colors.get(severity, "#999"), "text": message}]}
    try:
        import requests
        requests.post(webhook_url, json=payload, timeout=5)
        logger.info("✅ Slack alert sent")
    except Exception as e:
        logger.error(f"❌ Slack alert failed: {e}")
