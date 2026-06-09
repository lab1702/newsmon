from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


@dataclass(frozen=True, slots=True)
class NewsItem:
    source: str
    title: str
    url: str
    published: datetime  # timezone-aware
    summary: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def dedup_key(self) -> str:
        parts = urlsplit(self.url)
        host = parts.hostname or ""
        path = parts.path.rstrip("/")
        query = urlencode(
            sorted(
                (k, v)
                for k, v in parse_qsl(parts.query)
                if not k.lower().startswith("utm_")
            )
        )
        return urlunsplit(("", host.lower(), path, query, ""))
