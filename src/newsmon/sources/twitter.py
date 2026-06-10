from __future__ import annotations

import asyncio
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

import feedparser

from newsmon.models import NewsItem
from newsmon.sources.base import clean_text, fetch_text, published_from_feed

_TITLE_MAX = 500

NAME = "x"
INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
]


def normalize_to_x_url(raw: str) -> str:
    try:
        parts = urlsplit(raw)
    except ValueError:
        # A malformed authority (e.g. unterminated IPv6 literal) from a hostile
        # Nitter instance must degrade to no URL, not abort the whole feed.
        return ""
    # A missing/host-only link has no path to map onto x.com; return "" rather
    # than fabricating "https://x.com" (which would look like a real, openable item).
    if not parts.path.strip("/"):
        return ""
    return urlunsplit(("https", "x.com", parts.path, "", ""))


def parse_nitter(text: str) -> list[NewsItem]:
    feed = feedparser.parse(text)
    items: list[NewsItem] = []
    for entry in feed.entries:
        items.append(
            NewsItem(
                source=NAME,
                # The title comes from a third-party Nitter instance; sanitize it
                # (strip control/bidi escapes, cap length) before it reaches the UI.
                title=clean_text(entry.get("title", ""), max_len=_TITLE_MAX),
                url=normalize_to_x_url(entry.get("link", "")),
                published=published_from_feed(entry),
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
                text = await fetch_text(
                    client,
                    f"{base}/search/rss",
                    params={"f": "tweets", "q": topic},
                    # Nitter instances are untrusted third parties; don't follow
                    # their redirects — that would let a hostile instance 302 the
                    # shared client to an internal/link-local host (blind SSRF).
                    follow_redirects=False,
                )
            except Exception as exc:  # noqa: BLE001 - try next instance
                last_error = exc
                continue
            # First instance that responds is authoritative — an empty result
            # means "no tweets", not "instance down", so don't fall through.
            return await asyncio.to_thread(parse_nitter, text)
        if last_error:
            raise last_error
        return []
