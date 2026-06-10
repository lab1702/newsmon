from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from newsmon.models import NewsItem
from newsmon.sources.base import as_dict, as_list, fetch_text, utcnow

NAME = "reddit"
ENDPOINT = "https://www.reddit.com/search.json"
USER_AGENT = "newsmon/0.1 (breaking-news monitor)"


def parse_reddit(text: str) -> list[NewsItem]:
    data = json.loads(text)
    items: list[NewsItem] = []
    for child in as_list(as_dict(data.get("data")).get("children")):
        post = as_dict(as_dict(child).get("data"))
        if not post:  # malformed/non-dict child carries no usable post
            continue
        permalink = post.get("permalink")
        if isinstance(permalink, str) and permalink.startswith("/") and not permalink.startswith("//"):
            # Only a server-relative permalink is safe to concatenate; anything
            # else (a non-string, or "@evil.com/x" which would resolve to host
            # evil.com) falls back to a validated url so we never spoof the host.
            url = f"https://www.reddit.com{permalink}"
        else:
            raw_url = post.get("url")
            url = raw_url if isinstance(raw_url, str) else ""
        created = post.get("created_utc")
        try:
            published = (
                datetime.fromtimestamp(created, tz=timezone.utc)
                # A JSON boolean is an int subclass; left in, true → epoch 1
                # (1970) and the item is silently dropped by the recency filter.
                if isinstance(created, (int, float)) and not isinstance(created, bool)
                else utcnow()
            )
        except (TypeError, ValueError, OverflowError):
            # A malformed/non-numeric created_utc must not lose the whole batch.
            published = utcnow()
        raw_title = post.get("title")
        items.append(
            NewsItem(
                source=NAME,
                title=raw_title if isinstance(raw_title, str) and raw_title else "(untitled)",
                url=url,
                published=published,
                summary="",
                extra={
                    "subreddit": post.get("subreddit", ""),
                    "comments": post.get("num_comments", 0),
                    "external": post.get("url", ""),
                },
            )
        )
    return items


class RedditSource:
    name = NAME

    async def fetch(self, client, topic: str, since: datetime) -> list[NewsItem]:
        params = {"q": topic, "sort": "new", "limit": 50}
        text = await fetch_text(
            client, ENDPOINT, params=params, headers={"User-Agent": USER_AGENT}
        )
        return await asyncio.to_thread(parse_reddit, text)
