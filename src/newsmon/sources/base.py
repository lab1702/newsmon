from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Protocol

from newsmon.health import Health, SourceResult
from newsmon.models import NewsItem


class Source(Protocol):
    name: str

    async def fetch(self, client, topic: str, since: datetime) -> list[NewsItem]: ...


async def safe_fetch(
    source: Source,
    client,
    topic: str,
    since: datetime,
    timeout: float,
    slow_after: float,
) -> SourceResult:
    """Run one source's fetch with a timeout, never raising; report health."""
    loop = asyncio.get_running_loop()
    start = loop.time()
    try:
        items = await asyncio.wait_for(source.fetch(client, topic, since), timeout)
    except Exception as exc:  # noqa: BLE001 - sources must never crash the app
        elapsed = loop.time() - start
        return SourceResult(source.name, [], Health.FAILED, repr(exc), elapsed)
    elapsed = loop.time() - start
    health = Health.SLOW if elapsed > slow_after else Health.OK
    return SourceResult(source.name, items, health, None, elapsed)
