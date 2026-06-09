from __future__ import annotations

import json
from datetime import datetime

from newsmon.models import NewsItem

NAME = "hn"
ENDPOINT = "https://hn.algolia.com/api/v1/search_by_date"


def parse_hackernews(text: str) -> list[NewsItem]:
    data = json.loads(text)
    items: list[NewsItem] = []
    for hit in data.get("hits", []):
        object_id = hit.get("objectID", "")
        discussion = f"https://news.ycombinator.com/item?id={object_id}"
        url = hit.get("url") or discussion
        published = datetime.fromisoformat(hit["created_at"].replace("Z", "+00:00"))
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
        params = {"query": topic, "tags": "story", "hitsPerPage": 50}
        resp = await client.get(ENDPOINT, params=params)
        resp.raise_for_status()
        return parse_hackernews(resp.text)
