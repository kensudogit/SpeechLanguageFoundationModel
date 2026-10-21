import os
import time
from collections import defaultdict

_hits: dict[str, list[float]] = defaultdict(list)


def limit_per_minute() -> int:
    return int(os.getenv("RATE_LIMIT_PER_MIN", "30"))


def allow(key: str) -> bool:
    limit = limit_per_minute()
    if limit <= 0:
        return True
    now = time.time()
    recent = [stamp for stamp in _hits[key] if now - stamp < 60]
    if len(recent) >= limit:
        _hits[key] = recent
        return False
    recent.append(now)
    _hits[key] = recent
    return True
