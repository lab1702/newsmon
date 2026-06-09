from __future__ import annotations

import asyncio
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


class SeenTracker:
    """Tracks dedup keys across polls; the first poll establishes the baseline."""

    def __init__(self) -> None:
        self._seen: set[str] = set()
        self._baseline_set = False

    def mark_new(self, items: list[NewsItem]) -> list[NewsItem]:
        new: list[NewsItem] = []
        for item in items:
            key = item.dedup_key
            if key not in self._seen:
                self._seen.add(key)
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
