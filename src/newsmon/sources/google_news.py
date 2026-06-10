from __future__ import annotations

import asyncio
from datetime import datetime

import feedparser

from newsmon.models import NewsItem
from newsmon.sources.base import fetch_text, published_from_feed

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
                # The link is a Google News redirect (news.google.com/rss/articles/…),
                # not the publisher's URL. Unlike Bing's apiclick wrapper the target
                # isn't a query param — the newer format encodes it opaquely and can't
                # be recovered keyless — so we keep the redirect, which the browser
                # resolves on open. Consequence: the same story from `web` won't share
                # a dedup_key with `bing`/`gdelt`, so it can show as a cross-source dup.
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
        text = await fetch_text(client, ENDPOINT, params=params)
        return await asyncio.to_thread(parse_google_news, text)
