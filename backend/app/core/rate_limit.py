"""In-process sliding-window rate limiter for expensive endpoints.

Suitable for a single backend instance. For multiple replicas, move the counters
to a shared store (e.g. Redis) — see README "Deployment notes".
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request

from app.core.errors import RateLimitedError


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: float) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = int(window_seconds - (now - hits[0])) + 1
            raise RateLimitedError(
                "Too many requests. Please slow down and try again shortly.",
                details={"retry_after": retry_after},
            )
        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()


limiter = SlidingWindowLimiter()


def client_key(request: Request) -> str:
    # X-Client-Id is self-asserted, so the limit is keyed on IP as well.
    host = request.client.host if request.client else "unknown"
    return host


def rate_limit(bucket: str, limit_getter: Callable[[], int], window_seconds: float) -> Callable:
    async def dependency(request: Request) -> None:
        limiter.check(f"{bucket}:{client_key(request)}", limit_getter(), window_seconds)

    return dependency
