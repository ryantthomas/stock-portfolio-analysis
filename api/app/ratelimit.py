"""A small fixed-window rate limiter.

Deliberately dependency-free and in-process. That is sufficient for a single
container, which is how this app is meant to be deployed, but it means each
replica keeps its own counters: running N replicas allows roughly N times the
configured rate. A deployment that needs a real shared limit should put one in
front (a reverse proxy, an API gateway) rather than scaling this out.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class RateLimiter:
    """Allow at most `limit` hits per `window` seconds, per key."""

    def __init__(self, limit: int, window: float = 60.0, max_keys: int = 10_000) -> None:
        self.limit = limit
        self.window = window
        self.max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Record a hit. Returns (allowed, seconds_until_retry)."""
        if self.limit <= 0:
            return True, 0

        now = time.monotonic()
        cutoff = now - self.window

        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                hits = deque()
                # Bound memory: a flood of unique IPs must not grow this
                # dictionary without limit.
                if len(self._hits) >= self.max_keys:
                    self._evict_locked(cutoff)
                self._hits[key] = hits

            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= self.limit:
                retry_after = max(1, int(hits[0] + self.window - now) + 1)
                return False, retry_after

            hits.append(now)
            return True, 0

    def _evict_locked(self, cutoff: float) -> None:
        """Drop keys whose hits have all aged out. Caller must hold the lock."""
        stale = [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]
        for key in stale:
            del self._hits[key]
        if not stale:
            # Everything is active; clear the oldest half rather than refuse
            # service. Worst case a few clients get a fresh allowance.
            for key in list(self._hits)[: self.max_keys // 2]:
                del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
