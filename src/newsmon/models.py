from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


@dataclass(frozen=True)
class NewsItem:
    source: str
    title: str
    url: str
    published: datetime  # timezone-aware
    summary: str = ""
    extra: dict = field(default_factory=dict)

    @cached_property
    def dedup_key(self) -> str:
        # dedup_key is first evaluated in merge_items/SeenTracker, which run
        # OUTSIDE safe_fetch — so a non-string url (e.g. a JSON number that
        # slipped past a parser) or a malformed URL (an unterminated IPv6
        # literal) must degrade to the fallback key here, not crash the whole
        # poll for every source.
        url = self.url if isinstance(self.url, str) else ""
        try:
            parts = urlsplit(url)
            host = parts.hostname or ""
            path = parts.path.rstrip("/")
            query = urlencode(
                sorted(
                    (k, v)
                    for k, v in parse_qsl(parts.query)
                    if not k.lower().startswith("utm_")
                )
            )
            key = urlunsplit(("", host.lower(), path, query, ""))
        except ValueError:
            key = ""
        # URL-less items would all normalize to "" and collapse into one;
        # fall back to a per-item key so distinct items stay distinct.
        return key or f"{self.source}\x00{self.title}"
