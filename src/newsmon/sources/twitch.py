from __future__ import annotations

import asyncio
import json
from datetime import datetime
from urllib.parse import quote

from newsmon.models import NewsItem
from newsmon.sources.base import as_dict, as_list, fetch_text, parse_iso8601_utc

NAME = "twitch"
ENDPOINT = "https://gql.twitch.tv/gql"
# Public web Client-ID used by the Twitch website (unofficial, best-effort).
CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"

_GQL = """
query($q: String!) {
  searchFor(userQuery: $q, platform: "web", target: {index: CHANNEL}) {
    channels {
      edges {
        item {
          login
          displayName
          broadcastSettings { title }
          stream { id viewersCount createdAt }
        }
      }
    }
  }
}
"""


def parse_twitch(text: str) -> list[NewsItem]:
    data = json.loads(text)
    search = as_dict(as_dict(data.get("data")).get("searchFor"))
    edges = as_list(as_dict(search.get("channels")).get("edges"))
    items: list[NewsItem] = []
    for edge in edges:
        item = as_dict(as_dict(edge).get("item"))
        stream = as_dict(item.get("stream"))
        if not stream:  # skip offline channels (also coerces wrong-type values)
            continue
        created = stream.get("createdAt")
        if not created:
            continue
        try:
            published = parse_iso8601_utc(created)
        except ValueError:
            continue
        login = item.get("login", "")
        title = as_dict(item.get("broadcastSettings")).get("title", "") or item.get(
            "displayName", login
        )
        items.append(
            NewsItem(
                source=NAME,
                title=title,
                url=f"https://twitch.tv/{quote(login, safe='')}",
                published=published,
                summary="",
                extra={"viewers": stream.get("viewersCount", 0)},
            )
        )
    return items


class TwitchSource:
    name = NAME

    async def fetch(self, client, topic: str, since: datetime) -> list[NewsItem]:
        payload = {"query": _GQL, "variables": {"q": topic}}
        text = await fetch_text(
            client, ENDPOINT, method="POST", json=payload,
            headers={"Client-Id": CLIENT_ID},
        )
        return await asyncio.to_thread(parse_twitch, text)
