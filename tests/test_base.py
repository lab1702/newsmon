import asyncio
from datetime import datetime, timezone

from newsmon.health import Health
from newsmon.models import NewsItem
from newsmon.sources.base import safe_fetch

NOW = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)


class GoodSource:
    name = "good"

    async def fetch(self, client, topic, since):
        return [NewsItem("good", "t", "https://x/1", NOW)]


class BoomSource:
    name = "boom"

    async def fetch(self, client, topic, since):
        raise RuntimeError("kaboom")


class HangSource:
    name = "hang"

    async def fetch(self, client, topic, since):
        await asyncio.sleep(5)
        return []


async def test_safe_fetch_ok():
    r = await safe_fetch(GoodSource(), None, "quake", NOW, timeout=2, slow_after=10)
    assert r.health is Health.OK
    assert r.count == 1


async def test_safe_fetch_failure_is_captured():
    r = await safe_fetch(BoomSource(), None, "quake", NOW, timeout=2, slow_after=10)
    assert r.health is Health.FAILED
    assert "kaboom" in r.error
    assert r.items == []


async def test_safe_fetch_timeout_is_failure():
    r = await safe_fetch(HangSource(), None, "quake", NOW, timeout=0.05, slow_after=10)
    assert r.health is Health.FAILED


async def test_safe_fetch_slow_flag():
    r = await safe_fetch(GoodSource(), None, "quake", NOW, timeout=2, slow_after=-1)
    assert r.health is Health.SLOW
