from __future__ import annotations

from datetime import datetime
from urllib.parse import parse_qs, urlsplit

import feedparser

from newsmon.models import NewsItem
from newsmon.sources.base import fetch_text, published_from_feed

NAME = "bing"
ENDPOINT = "https://www.bing.com/news/search"
# Bing serves the RSS feed only to browser-like clients.
USER_AGENT = "Mozilla/5.0 (compatible; newsmon/1.0)"


def _unwrap(link: str) -> str:
    """Bing wraps each article link in an apiclick redirect; the real article
    URL rides in the `url` query parameter. Fall back to the link itself.
    `parse_qs` already percent-decodes the value, so don't unquote it again."""
    target = parse_qs(urlsplit(link).query).get("url")
    return target[0] if target else link


def parse_bing_news(text: str) -> list[NewsItem]:
    feed = feedparser.parse(text)
    items: list[NewsItem] = []
    for entry in feed.entries:
        items.append(
            NewsItem(
                source=NAME,
                title=entry.get("title", "(untitled)"),
                url=_unwrap(entry.get("link", "")),
                published=published_from_feed(entry),
                summary=entry.get("summary", ""),
                extra={"outlet": entry.get("news_source", "")},
            )
        )
    return items


class BingNewsSource:
    name = NAME

    async def fetch(self, client, topic: str, since: datetime) -> list[NewsItem]:
        params = {"q": topic, "format": "rss"}
        text = await fetch_text(
            client, ENDPOINT, params=params, headers={"User-Agent": USER_AGENT}
        )
        return parse_bing_news(text)
