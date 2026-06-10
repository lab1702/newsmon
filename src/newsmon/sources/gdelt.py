from __future__ import annotations

import json
from datetime import datetime, timezone

from newsmon.models import NewsItem

NAME = "gdelt"
ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"


def _published(seendate: str) -> datetime:
    # GDELT timestamps look like "20260609T113000Z" and are always UTC.
    return datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def parse_gdelt(text: str) -> list[NewsItem]:
    data = json.loads(text)
    items: list[NewsItem] = []
    for art in data.get("articles", []):
        items.append(
            NewsItem(
                source=NAME,
                title=art.get("title") or "(untitled)",
                url=art.get("url", ""),
                published=_published(art["seendate"]),
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
        resp = await client.get(ENDPOINT, params=params)
        resp.raise_for_status()
        return parse_gdelt(resp.text)
