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
        permalink = post.get("permalink", "")
        url = f"https://www.reddit.com{permalink}" if permalink else post.get("url", "")
        created = post.get("created_utc")
        try:
            published = (
                datetime.fromtimestamp(created, tz=timezone.utc)
                if created is not None
                else utcnow()
            )
        except (TypeError, ValueError, OverflowError):
            # A malformed/non-numeric created_utc must not lose the whole batch.
            published = utcnow()
        items.append(
            NewsItem(
                source=NAME,
                title=post.get("title") or "(untitled)",
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
