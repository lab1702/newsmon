from __future__ import annotations

from datetime import datetime

import feedparser

from newsmon.models import NewsItem
from newsmon.sources.base import published_from_feed

NAME = "web"
ENDPOINT = "https://news.google.com/rss/search"


def parse_google_news(text: str) -> list[NewsItem]:
    feed = feedparser.parse(text)
    items: list[NewsItem] = []
    for entry in feed.entries:
        outlet = ""
        source = getattr(entry, "source", None)
        if source is not None:
            outlet = getattr(source, "title", "") or ""
        items.append(
            NewsItem(
                source=NAME,
                title=entry.get("title", "(untitled)"),
                url=entry.get("link", ""),
                published=published_from_feed(entry),
                summary=entry.get("summary", ""),
                extra={"outlet": outlet},
            )
        )
    return items


class GoogleNewsSource:
    name = NAME

    async def fetch(self, client, topic: str, since: datetime) -> list[NewsItem]:
        params = {"q": topic, "hl": "en-US", "gl": "US", "ceid": "US:en"}
        resp = await client.get(ENDPOINT, params=params)
        resp.raise_for_status()
        return parse_google_news(resp.text)
