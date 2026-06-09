"""newsmon sources and registry."""

from __future__ import annotations

from newsmon.sources.base import Source, safe_fetch
from newsmon.sources.google_news import GoogleNewsSource
from newsmon.sources.hackernews import HackerNewsSource
from newsmon.sources.reddit import RedditSource
from newsmon.sources.twitch import TwitchSource
from newsmon.sources.twitter import TwitterSource
from newsmon.sources.youtube import YouTubeSource

_REGISTRY = {
    "web": GoogleNewsSource,
    "hn": HackerNewsSource,
    "reddit": RedditSource,
    "youtube": YouTubeSource,
    "twitch": TwitchSource,
    "x": TwitterSource,
}
ALL_SOURCE_NAMES = list(_REGISTRY)

__all__ = ["ALL_SOURCE_NAMES", "Source", "build_sources", "safe_fetch"]


def build_sources(names: list[str] | None) -> list[Source]:
    selected = ALL_SOURCE_NAMES if names is None else names
    unknown = [n for n in selected if n not in _REGISTRY]
    if unknown:
        raise ValueError(f"unknown source(s): {', '.join(unknown)}")
    return [_REGISTRY[n]() for n in ALL_SOURCE_NAMES if n in selected]
