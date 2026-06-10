from __future__ import annotations

import json
from datetime import datetime

from newsmon.models import NewsItem
from newsmon.sources.base import parse_iso8601_utc

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
    edges = (
        data.get("data", {})
        .get("searchFor", {})
        .get("channels", {})
        .get("edges", [])
    )
    items: list[NewsItem] = []
    for edge in edges:
        item = edge.get("item") or {}
        stream = item.get("stream")
        if not stream:  # skip offline channels
            continue
        created = stream.get("createdAt")
        if not created:
            continue
        try:
            published = parse_iso8601_utc(created)
        except ValueError:
            continue
        login = item.get("login", "")
        title = (item.get("broadcastSettings") or {}).get("title", "") or item.get(
            "displayName", login
        )
        items.append(
            NewsItem(
                source=NAME,
                title=title,
                url=f"https://twitch.tv/{login}",
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
        resp = await client.post(
            ENDPOINT, json=payload, headers={"Client-Id": CLIENT_ID}
        )
        resp.raise_for_status()
        return parse_twitch(resp.text)
