from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from newsmon.models import NewsItem


class Health(str, Enum):
    OK = "ok"
    SLOW = "slow"
    FAILED = "failed"


@dataclass
class SourceResult:
    name: str
    items: list[NewsItem]
    health: Health
    error: str | None = None
    elapsed: float = 0.0

    @property
    def count(self) -> int:
        return len(self.items)
