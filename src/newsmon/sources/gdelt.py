from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from newsmon.models import NewsItem
from newsmon.sources.base import as_dict, as_list, fetch_text

NAME = "gdelt"
ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"


def _published(seendate: str) -> datetime:
    # GDELT timestamps look like "20260609T113000Z" and are always UTC.
    return datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def parse_gdelt(text: str) -> list[NewsItem]:
    data = json.loads(text)
    items: list[NewsItem] = []
    for art in as_list(data.get("articles")):
        art = as_dict(art)
        seendate = art.get("seendate")
        if not isinstance(seendate, str) or not seendate:
            # A non-string seendate (JSON number) reaches strptime and raises
            # TypeError, not the caught ValueError; skip it, keep the batch.
            continue
        try:
            published = _published(seendate)
        except ValueError:
            continue
        raw_title = art.get("title")
        raw_url = art.get("url")
        items.append(
            NewsItem(
                source=NAME,
                title=raw_title if isinstance(raw_title, str) and raw_title else "(untitled)",
                url=raw_url if isinstance(raw_url, str) else "",
                published=published,
                summary="",
                extra={
                    "domain": art.get("domain", ""),
                    "country": art.get("sourcecountry", ""),
                },
            )
        )
    return items


class GdeltSource:
    name = NAME

    async def fetch(self, client, topic: str, since: datetime) -> list[NewsItem]:
        params = {
            "query": topic,
            "mode": "artlist",
            "format": "json",
            "sort": "datedesc",
            "maxrecords": 75,
        }
        text = await fetch_text(client, ENDPOINT, params=params)
        return await asyncio.to_thread(parse_gdelt, text)
