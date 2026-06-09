from __future__ import annotations

from datetime import datetime

from newsmon.health import SourceResult
from newsmon.models import NewsItem


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
