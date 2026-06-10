from __future__ import annotations

import html
import re
from datetime import datetime
from urllib.parse import urlsplit

import feedparser

from newsmon.models import NewsItem
from newsmon.sources.base import published_from_feed

NAME = "masto"
INSTANCE = "https://mastodon.social"

_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_TITLE_MAX = 200


def hashtag(topic: str) -> str:
    """Mastodon serves one RSS feed per hashtag, and hashtags are a single
    alphanumeric token — so collapse the topic to lowercase letters/digits."""
    return re.sub(r"[^0-9a-z]", "", topic.lower())


def _text(summary: str) -> str:
    """Mastodon posts arrive as an HTML body and have no plain title."""
    stripped = _WS.sub(" ", html.unescape(_TAGS.sub("", summary))).strip()
    if len(stripped) > _TITLE_MAX:
        stripped = stripped[: _TITLE_MAX - 1].rstrip() + "…"
    return stripped


def _author(link: str) -> str:
    """A post URL is https://<instance>/@<handle>/<id>; rebuild @handle@instance."""
    parts = urlsplit(link)
    segments = [s for s in parts.path.split("/") if s]
    handle = segments[0] if segments and segments[0].startswith("@") else ""
    if not handle or not parts.hostname:
        return ""
    return f"{handle}@{parts.hostname}"


def parse_mastodon(text: str) -> list[NewsItem]:
    feed = feedparser.parse(text)
    items: list[NewsItem] = []
    for entry in feed.entries:
        link = entry.get("link", "")
        items.append(
            NewsItem(
                source=NAME,
                title=_text(entry.get("summary", "")) or "(post)",
                url=link,
                published=published_from_feed(entry),
                summary="",
                extra={"author": _author(link)},
            )
        )
    return items


class MastodonSource:
    name = NAME

    async def fetch(self, client, topic: str, since: datetime) -> list[NewsItem]:
        tag = hashtag(topic)
        if not tag:
            return []
        resp = await client.get(f"{INSTANCE}/tags/{tag}.rss")
        resp.raise_for_status()
        return parse_mastodon(resp.text)
