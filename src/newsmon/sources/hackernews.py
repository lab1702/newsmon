from __future__ import annotations

import asyncio
import json
from datetime import datetime
from urllib.parse import quote

from newsmon.models import NewsItem
from newsmon.sources.base import as_dict, as_list, fetch_text, parse_iso8601_utc

NAME = "hn"
ENDPOINT = "https://hn.algolia.com/api/v1/search_by_date"


def parse_hackernews(text: str) -> list[NewsItem]:
    data = json.loads(text)
    items: list[NewsItem] = []
    for hit in as_list(data.get("hits")):
        hit = as_dict(hit)
        created = hit.get("created_at")
        if not isinstance(created, str) or not created:
            # A truthy non-string created_at would reach parse_iso8601_utc and
            # raise AttributeError (not the caught ValueError), aborting the batch.
            continue
        try:
            published = parse_iso8601_utc(created)
        except ValueError:
            continue
        object_id = hit.get("objectID", "")
        discussion = (
            f"https://news.ycombinator.com/item?id={quote(str(object_id), safe='')}"
        )
        raw_url = hit.get("url")
        url = raw_url if isinstance(raw_url, str) and raw_url else discussion
        raw_title = hit.get("title")
        items.append(
            NewsItem(
                source=NAME,
                title=raw_title if isinstance(raw_title, str) and raw_title else "(untitled)",
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
        text = await fetch_text(client, ENDPOINT, params=params)
        return await asyncio.to_thread(parse_hackernews, text)
