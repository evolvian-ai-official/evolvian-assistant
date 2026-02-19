import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock

from fastapi import HTTPException, Request, status


@dataclass
class _Bucket:
    window_seconds: int
    hits: deque[float] = field(default_factory=deque)


_BUCKETS: dict[str, _Bucket] = {}
_LOCK = Lock()
_CALLS = 0
_CLEANUP_EVERY = 256


def get_request_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _prune_bucket(bucket: _Bucket, now: float) -> None:
    cutoff = now - bucket.window_seconds
    while bucket.hits and bucket.hits[0] <= cutoff:
        bucket.hits.popleft()


def _cleanup(now: float) -> None:
    stale_keys: list[str] = []
    for key, bucket in _BUCKETS.items():
        _prune_bucket(bucket, now)
        if not bucket.hits:
            stale_keys.append(key)
    for key in stale_keys:
        _BUCKETS.pop(key, None)


def enforce_rate_limit(
    *,
    scope: str,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    if limit <= 0 or window_seconds <= 0:
        return

    bucket_key = f"{scope}:{key}"
    now = time.monotonic()

    global _CALLS
    with _LOCK:
        _CALLS += 1
        bucket = _BUCKETS.get(bucket_key)
        if bucket is None or bucket.window_seconds != window_seconds:
            bucket = _Bucket(window_seconds=window_seconds)
            _BUCKETS[bucket_key] = bucket

        _prune_bucket(bucket, now)
        if len(bucket.hits) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="too_many_requests",
            )

        bucket.hits.append(now)

        if _CALLS % _CLEANUP_EVERY == 0:
            _cleanup(now)
