from __future__ import annotations

import json
from datetime import datetime

from newsmon.models import NewsItem
from newsmon.sources.base import parse_iso8601_utc

NAME = "hn"
ENDPOINT = "https://hn.algolia.com/api/v1/search_by_date"


def parse_hackernews(text: str) -> list[NewsItem]:
    data = json.loads(text)
    items: list[NewsItem] = []
    for hit in data.get("hits", []):
        created = hit.get("created_at")
        if not created:
            continue
        try:
            published = parse_iso8601_utc(created)
        except ValueError:
            continue
        object_id = hit.get("objectID", "")
        discussion = f"https://news.ycombinator.com/item?id={object_id}"
        url = hit.get("url") or discussion
        items.append(
            NewsItem(
                source=NAME,
                title=hit.get("title") or "(untitled)",
                url=url,
                published=published,
                summary="",
                extra={
                    "points": hit.get("points", 0),
                    "author": hit.get("author", ""),
                    "discussion": discussion,
                },
            )
        )
    return items


class HackerNewsSource:
    name = NAME

    async def fetch(self, client, topic: str, since: datetime) -> list[NewsItem]:
        params = {
            "query": topic,
            "tags": "story",
            "hitsPerPage": 50,
            "numericFilters": f"created_at_i>{int(since.timestamp())}",
        }
        resp = await client.get(ENDPOINT, params=params)
        resp.raise_for_status()
        return parse_hackernews(resp.text)
