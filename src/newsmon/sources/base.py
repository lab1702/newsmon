from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Protocol

from newsmon.health import Health, SourceResult
from newsmon.models import NewsItem


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def published_from_feed(entry) -> datetime:
    """Timestamp from a feedparser entry, falling back to now() when absent."""
    parsed = getattr(entry, "published_parsed", None)
    if parsed is None:
        return utcnow()
    try:
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    except (ValueError, TypeError):
        # An out-of-range struct_time (e.g. month=13) would otherwise abort the
        # whole feed; fall back to now() like the missing-timestamp case.
        return utcnow()


def parse_iso8601_utc(value: str) -> datetime:
    """Parse an ISO-8601 timestamp, normalizing a trailing 'Z' to +00:00."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


MAX_RESPONSE_BYTES = 8 * 1024 * 1024  # 8 MiB ceiling per response


async def fetch_text(
    client,
    url: str,
    *,
    method: str = "GET",
    max_bytes: int = MAX_RESPONSE_BYTES,
    **kwargs,
) -> str:
    """Stream a request to text, aborting if the body exceeds ``max_bytes`` so a
    pathological response can't exhaust memory before we parse it. Centralizes
    ``raise_for_status`` for every source."""
    async with client.stream(method, url, **kwargs) as resp:
        resp.raise_for_status()
        chunks: list[bytes] = []
        total = 0
        async for chunk in resp.aiter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"response from {url} exceeded {max_bytes} bytes")
            chunks.append(chunk)
        encoding = resp.encoding or "utf-8"
    return b"".join(chunks).decode(encoding, errors="replace")


class Source(Protocol):
    name: str

    async def fetch(self, client, topic: str, since: datetime) -> list[NewsItem]: ...


async def safe_fetch(
    source: Source,
    client,
    topic: str,
    since: datetime,
    timeout: float,
    slow_after: float,
) -> SourceResult:
    """Run one source's fetch with a timeout, never raising; report health."""
    loop = asyncio.get_running_loop()
    start = loop.time()
    try:
        items = await asyncio.wait_for(source.fetch(client, topic, since), timeout)
    except Exception as exc:  # noqa: BLE001 - sources must never crash the app
        elapsed = loop.time() - start
        return SourceResult(source.name, [], Health.FAILED, repr(exc), elapsed)
    elapsed = loop.time() - start
    health = Health.SLOW if elapsed > slow_after else Health.OK
    return SourceResult(source.name, items, health, None, elapsed)
