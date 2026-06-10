from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from newsmon.models import NewsItem
from newsmon.sources.base import fetch_text

NAME = "youtube"
# sp="CAI=" → encoded to sp=CAI%3D on the wire, which sorts results by upload date
ENDPOINT = "https://www.youtube.com/results"
_DATA_RE = re.compile(r"ytInitialData\s*=\s*(\{.*?\})\s*;\s*</script>", re.DOTALL)
_REL_RE = re.compile(r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago")
_UNIT_DAYS = {
    "second": 1 / 86400,
    "minute": 1 / 1440,
    "hour": 1 / 24,
    "day": 1,
    "week": 7,
    "month": 30,
    "year": 365,
}


def parse_relative_time(text: str, now: datetime) -> datetime | None:
    match = _REL_RE.search(text or "")
    if not match:
        return None
    qty = int(match.group(1))
    unit = match.group(2)
    if unit in ("second", "minute", "hour"):
        seconds = qty * _UNIT_DAYS[unit] * 86400
        return now - timedelta(seconds=round(seconds))
    return now - timedelta(days=qty * _UNIT_DAYS[unit])


def _walk_video_renderers(node):
    if isinstance(node, dict):
        if "videoRenderer" in node:
            # A videoRenderer holds scalar fields, not nested videoRenderers, so
            # stop here rather than descending into its own subtree.
            yield node["videoRenderer"]
            return
        for value in node.values():
            yield from _walk_video_renderers(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_video_renderers(value)


def _text(node: dict, key: str) -> str:
    runs = (node.get(key) or {}).get("runs") or []
    return runs[0]["text"] if runs else ""


def parse_youtube(html: str, now: datetime) -> list[NewsItem]:
    match = _DATA_RE.search(html)
    if not match:
        return []
    data = json.loads(match.group(1))
    items: list[NewsItem] = []
    for vr in _walk_video_renderers(data):
        video_id = vr.get("videoId")
        if not video_id:
            continue
        rel = (vr.get("publishedTimeText") or {}).get("simpleText", "")
        published = parse_relative_time(rel, now)
        if published is None:
            continue
        items.append(
            NewsItem(
                source=NAME,
                title=_text(vr, "title"),
                url=f"https://www.youtube.com/watch?v={video_id}",
                published=published,
                summary="",
                extra={"channel": _text(vr, "ownerText")},
            )
        )
    return items


class YouTubeSource:
    name = NAME

    async def fetch(self, client, topic: str, since: datetime) -> list[NewsItem]:
        params = {"search_query": topic, "sp": "CAI="}
        text = await fetch_text(
            client,
            ENDPOINT,
            params=params,
            headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        return parse_youtube(text, datetime.now(timezone.utc))
