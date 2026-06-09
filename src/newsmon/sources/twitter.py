from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import feedparser

from newsmon.models import NewsItem

NAME = "x"
INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
]


def normalize_to_x_url(raw: str) -> str:
    parts = urlsplit(raw)
    return urlunsplit(("https", "x.com", parts.path, "", ""))


def _published(entry) -> datetime:
    parsed = getattr(entry, "published_parsed", None)
    if parsed is None:
        return datetime.now(timezone.utc)
    return datetime(*parsed[:6], tzinfo=timezone.utc)


def parse_nitter(text: str) -> list[NewsItem]:
    feed = feedparser.parse(text)
    items: list[NewsItem] = []
    for entry in feed.entries:
        items.append(
            NewsItem(
                source=NAME,
                title=entry.get("title", ""),
                url=normalize_to_x_url(entry.get("link", "")),
                published=_published(entry),
                summary="",
                extra={"author": entry.get("author", "")},
            )
        )
    return items


class TwitterSource:
    name = NAME

    async def fetch(self, client, topic: str, since: datetime) -> list[NewsItem]:
        last_error: Exception | None = None
        for base in INSTANCES:
            try:
                resp = await client.get(
                    f"{base}/search/rss", params={"f": "tweets", "q": topic}
                )
                resp.raise_for_status()
                items = parse_nitter(resp.text)
                if items:
                    return items
            except Exception as exc:  # noqa: BLE001 - try next instance
                last_error = exc
        if last_error:
            raise last_error
        return []
