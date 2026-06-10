from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import datetime

from newsmon.health import SourceResult
from newsmon.models import NewsItem
from newsmon.sources.base import safe_fetch


def merge_items(results: list[SourceResult], since: datetime) -> list[NewsItem]:
    """Flatten, drop items older than `since`, dedup by key (first wins), newest first."""
    seen: set[str] = set()
    out: list[NewsItem] = []
    for result in results:
        for item in result.items:
            if item.published < since:
                continue
            key = item.dedup_key
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
    out.sort(key=lambda i: i.published, reverse=True)
    return out


MAX_SEEN_KEYS = 50_000  # cap sits far above any realistic recency window


class SeenTracker:
    """Tracks dedup keys across polls; the first poll establishes the baseline.
    Keys are capped with oldest-first eviction so a long-running monitor can't
    grow the set without bound; the cap is large enough that evicted keys are
    always well outside the recency window and won't reappear to be re-flagged."""

    def __init__(self, max_keys: int = MAX_SEEN_KEYS) -> None:
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._max_keys = max_keys
        self._baseline_set = False

    def mark_new(self, items: list[NewsItem]) -> list[NewsItem]:
        new: list[NewsItem] = []
        for item in items:
            key = item.dedup_key
            if key in self._seen:
                continue
            self._seen[key] = None
            if len(self._seen) > self._max_keys:
                self._seen.popitem(last=False)
            if self._baseline_set:
                new.append(item)
        self._baseline_set = True
        return new


async def poll_sources(
    sources,
    client,
    topic: str,
    since: datetime,
    timeout: float,
    slow_after: float,
):
    """Fetch every source concurrently; one result per source, never raising."""
    tasks = [
        safe_fetch(s, client, topic, since, timeout, slow_after) for s in sources
    ]
    return await asyncio.gather(*tasks)
