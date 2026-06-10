from __future__ import annotations

import asyncio
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

import feedparser

from newsmon.models import NewsItem
from newsmon.sources.base import fetch_text, published_from_feed

NAME = "bing"
ENDPOINT = "https://www.bing.com/news/search"
# Bing serves the RSS feed only to browser-like clients.
USER_AGENT = "Mozilla/5.0 (compatible; newsmon/1.0)"


def _is_http_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        # e.g. an unterminated IPv6 literal — urlsplit raises ValueError, which
        # would otherwise surface later in dedup_key (outside safe_fetch).
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def _unwrap(link: str) -> str:
    """Bing wraps each article link in an apiclick redirect; the real article
    URL rides in the `url` query parameter. Fall back to the link itself.
    `parse_qs` already percent-decodes the value, so don't unquote it again.

    The unwrapped value is attacker-influenced (it comes straight from the feed),
    so reject anything that isn't a well-formed http(s) URL: a malformed IPv6
    literal would crash dedup_key, and a mailto:/data: scheme would render as a
    dead or misleading headline."""
    try:
        target = parse_qs(urlsplit(link).query).get("url")
    except ValueError:
        target = None
    candidate = target[0] if target else link
    return candidate if _is_http_url(candidate) else ""


def parse_bing_news(text: str) -> list[NewsItem]:
    feed = feedparser.parse(text)
    items: list[NewsItem] = []
    for entry in feed.entries:
        items.append(
            NewsItem(
                source=NAME,
                title=entry.get("title") or "(untitled)",
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
        return await asyncio.to_thread(parse_bing_news, text)
