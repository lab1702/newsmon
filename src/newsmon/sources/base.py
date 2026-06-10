from __future__ import annotations

import asyncio
import re
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
    """Parse an ISO-8601 timestamp as timezone-aware UTC.

    A trailing 'Z' is normalized to +00:00; a value carrying no offset at all is
    assumed UTC. Returning a naive datetime would slip past the callers' guards
    and later crash the tz-aware comparison in ``merge_items`` (which runs outside
    ``safe_fetch``), taking down the whole poll for every source.
    """
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


# Bidirectional-override and C0/C1 control characters are stripped from any
# untrusted feed text before it reaches the terminal: a hostile (e.g. federated)
# source can otherwise embed raw ANSI/BEL escapes to corrupt the screen, or a
# U+202E RTL override to visually spoof a headline.
_BIDI_RE = re.compile("[\u200e\u200f\u202a-\u202e\u2066-\u2069]")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_WS_RE = re.compile(r"\s+")


def clean_text(value: str, max_len: int | None = None) -> str:
    """Sanitize untrusted feed text for terminal rendering: drop bidi-override
    chars, replace C0/C1 controls (incl. tab/newline) with a space so adjacent
    words don't fuse, collapse runs of whitespace, and optionally truncate with
    an ellipsis."""
    text = _BIDI_RE.sub("", value)
    text = _CONTROL_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    if max_len is not None and len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def as_list(value) -> list:
    """Coerce a JSON value to a list, returning [] for anything else.

    The ``value or []`` idiom only guards against falsy values; a truthy-but-
    wrong-type field (e.g. ``{"articles": "error"}`` from an upstream error page
    or schema drift) would otherwise be iterated as a string and crash the parser
    on the next ``.get()``. This skips the bad field instead of nuking the source.
    """
    return value if isinstance(value, list) else []


def as_dict(value) -> dict:
    """Coerce a JSON value to a dict, returning {} for anything else. See as_list."""
    return value if isinstance(value, dict) else {}


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
