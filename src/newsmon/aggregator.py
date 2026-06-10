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
    grow the set without bound. A poll arrives newest-first (merge_items sorts
    descending), so keys are inserted in reverse — oldest-first — to keep the
    OrderedDict ordered by recency; popitem(last=False) then drops the genuinely
    oldest key, which leaves the recency window first. Eviction runs after the
    whole poll is recorded so a key just inserted this poll is never dropped
    (the per-source item cap keeps a poll far below max_keys)."""

    def __init__(self, max_keys: int = MAX_SEEN_KEYS) -> None:
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._max_keys = max_keys
        self._baseline_set = False

    def mark_new(self, items: list[NewsItem]) -> list[NewsItem]:
        new: list[NewsItem] = []
        # Insert oldest-first (items are newest-first) so recency == queue order.
        for item in reversed(items):
            key = item.dedup_key
            if key not in self._seen and self._baseline_set:
                new.append(item)
            # Refresh recency even for an already-seen key so a still-arriving
            # item is not evicted as if it were stale.
            self._seen[key] = None
            self._seen.move_to_end(key)
        # Evict AFTER the full poll so eviction can never discard a key we just
        # inserted; drop from the front (oldest) until back within the cap.
        while len(self._seen) > self._max_keys:
            self._seen.popitem(last=False)
        # Don't let an empty first poll (e.g. started offline) establish the
        # baseline against nothing — that would flag every item of the next
        # successful poll as "new" and ring the bell.
        if items:
            self._baseline_set = True
        new.reverse()  # restore newest-first to match merge order
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
