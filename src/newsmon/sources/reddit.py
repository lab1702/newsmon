from __future__ import annotations

import json
from datetime import datetime, timezone

from newsmon.models import NewsItem
from newsmon.sources.base import utcnow

NAME = "reddit"
ENDPOINT = "https://www.reddit.com/search.json"
USER_AGENT = "newsmon/0.1 (breaking-news monitor)"


def parse_reddit(text: str) -> list[NewsItem]:
    data = json.loads(text)
    items: list[NewsItem] = []
    for child in data.get("data", {}).get("children", []):
        post = child.get("data", {})
        permalink = post.get("permalink", "")
        url = f"https://www.reddit.com{permalink}" if permalink else post.get("url", "")
        created = post.get("created_utc")
        published = (
            datetime.fromtimestamp(created, tz=timezone.utc) if created else utcnow()
        )
        items.append(
            NewsItem(
                source=NAME,
                title=post.get("title", "(untitled)"),
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
        resp = await client.get(
            ENDPOINT, params=params, headers={"User-Agent": USER_AGENT}
        )
        resp.raise_for_status()
        return parse_reddit(resp.text)
