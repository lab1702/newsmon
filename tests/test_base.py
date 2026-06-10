import asyncio
from datetime import datetime, timezone

import pytest
from conftest import FakeStreamClient

from newsmon.health import Health
from newsmon.models import NewsItem
from newsmon.sources.base import (
    as_dict,
    as_list,
    fetch_text,
    published_from_feed,
    safe_fetch,
)

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


async def test_fetch_text_returns_decoded_body():
    client = FakeStreamClient("hello world", chunk_size=4)
    assert await fetch_text(client, "https://x/feed") == "hello world"


async def test_fetch_text_aborts_oversized_response():
    client = FakeStreamClient("x" * 10_000, chunk_size=1024)
    with pytest.raises(ValueError):
        await fetch_text(client, "https://x/feed", max_bytes=2048)


async def test_fetch_text_raises_for_status():
    client = FakeStreamClient("nope", status=503)
    with pytest.raises(RuntimeError):
        await fetch_text(client, "https://x/feed")


class _Entry:
    def __init__(self, published_parsed):
        self.published_parsed = published_parsed


def test_published_from_feed_out_of_range_falls_back_to_now():
    # An out-of-range struct_time (month=13) must not abort the whole feed.
    before = datetime.now(timezone.utc)
    got = published_from_feed(_Entry((2026, 13, 1, 0, 0, 0, 0, 0, 0)))
    assert got >= before
    assert got.tzinfo is not None


def test_published_from_feed_uses_valid_timestamp():
    got = published_from_feed(_Entry((2026, 6, 9, 11, 30, 0, 0, 0, 0)))
    assert got == datetime(2026, 6, 9, 11, 30, tzinfo=timezone.utc)


def test_as_list_passes_lists_through_and_rejects_other_types():
    assert as_list([1, 2]) == [1, 2]
    # Truthy-but-wrong-type values (a string, an int, a dict) coerce to [] so a
    # parser iterating the result can't crash on a char or a non-iterable.
    assert as_list("error") == []
    assert as_list(123) == []
    assert as_list({"a": 1}) == []
    assert as_list(None) == []


def test_as_dict_passes_dicts_through_and_rejects_other_types():
    assert as_dict({"a": 1}) == {"a": 1}
    assert as_dict("oops") == {}
    assert as_dict([1, 2]) == {}
    assert as_dict(None) == {}
