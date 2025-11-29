"""Simple in-memory rate limiting helper."""

from __future__ import annotations

import collections
import time
from typing import DefaultDict, List

WINDOW_SECONDS = 600
LIMIT = 10

_hits: DefaultDict[str, List[float]] = collections.defaultdict(list)


def allow(identifier: str, *, limit: int = LIMIT, window: int = WINDOW_SECONDS) -> bool:
    """Return True if the identifier is allowed to perform an action."""
    now = time.time()
    queue = _hits[identifier]

    while queue and now - queue[0] > window:
        queue.pop(0)

    if len(queue) >= limit:
        return False

    queue.append(now)
    return True


def reset() -> None:
    """Reset rate-limiting state (useful for tests)."""
    _hits.clear()
