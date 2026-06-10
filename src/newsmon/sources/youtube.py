from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from newsmon.models import NewsItem
from newsmon.sources.base import fetch_text

NAME = "youtube"
# sp="CAI=" → encoded to sp=CAI%3D on the wire, which sorts results by upload date
ENDPOINT = "https://www.youtube.com/results"
_DATA_MARKER = re.compile(r"ytInitialData\s*=\s*")
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
    if not isinstance(text, str):
        # publishedTimeText.simpleText may arrive as a non-string on schema
        # drift; the regex search would raise TypeError. Treat as unparseable.
        return None
    match = _REL_RE.search(text or "")
    if not match:
        return None
    qty = int(match.group(1))
    unit = match.group(2)
    try:
        if unit in ("second", "minute", "hour"):
            seconds = qty * _UNIT_DAYS[unit] * 86400
            return now - timedelta(seconds=round(seconds))
        return now - timedelta(days=qty * _UNIT_DAYS[unit])
    except OverflowError:
        # An absurd digit run ("9999…99 years ago") overflows timedelta; treat it
        # as unparseable rather than letting it abort the whole feed.
        return None


def _walk_video_renderers(node):
    """Yield every videoRenderer dict. Iterative (explicit stack) so a deeply
    nested ytInitialData payload can't exhaust the recursion limit. Children are
    pushed in reverse so popping preserves document order."""
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if "videoRenderer" in current:
                # A videoRenderer holds scalar fields, not nested videoRenderers,
                # so stop here rather than descending into its own subtree. A
                # non-dict value (schema drift) is dropped, not yielded — callers
                # do vr.get(...) and would otherwise crash on the whole walk.
                vr = current["videoRenderer"]
                if isinstance(vr, dict):
                    yield vr
                continue
            stack.extend(reversed(list(current.values())))
        elif isinstance(current, list):
            stack.extend(reversed(current))


def _text(node: dict, key: str) -> str:
    # YouTube text fields are run-arrays; the full string is every run joined,
    # so reading only runs[0] would truncate multi-run titles/channel names.
    # Every level is type-checked: a non-dict field, non-list runs, a bare-string
    # run, or a numeric run text are all coerced rather than crashing the parse.
    field = node.get(key)
    runs = field.get("runs") if isinstance(field, dict) else None
    runs = runs if isinstance(runs, list) else []
    return "".join(
        str(run.get("text", "")) for run in runs if isinstance(run, dict)
    )


def _extract_initial_data(html: str) -> str | None:
    """Return the `ytInitialData = {...}` object as raw JSON via a brace-balanced
    scan (string-aware), rather than a regex that assumes a `};</script>` suffix
    — YouTube periodically appends more script after the assignment."""
    marker = _DATA_MARKER.search(html)
    if not marker:
        return None
    start = html.find("{", marker.end())
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(html)):
        ch = html[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return html[start : i + 1]
    return None


def parse_youtube(html: str, now: datetime) -> list[NewsItem]:
    raw = _extract_initial_data(html)
    if raw is None:
        return []
    data = json.loads(raw)
    items: list[NewsItem] = []
    for vr in _walk_video_renderers(data):
        video_id = vr.get("videoId")
        if not video_id:
            continue
        ptt = vr.get("publishedTimeText")
        rel = ptt.get("simpleText", "") if isinstance(ptt, dict) else ""
        published = parse_relative_time(rel, now)
        if published is None:
            continue
        items.append(
            NewsItem(
                source=NAME,
                title=_text(vr, "title"),
                url=f"https://www.youtube.com/watch?v={quote(str(video_id), safe='')}",
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
        # Parse off the event loop: a large/pathological body would otherwise
        # block the single-threaded UI past the safe_fetch timeout.
        return await asyncio.to_thread(
            parse_youtube, text, datetime.now(timezone.utc)
        )
