import asyncio
from datetime import datetime, timezone

import pytest
from conftest import FakeStreamClient

from newsmon.health import Health
from newsmon.models import NewsItem
from newsmon.sources.base import (
    as_dict,
    as_list,
    clean_text,
    fetch_text,
    parse_iso8601_utc,
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


def test_parse_iso8601_utc_normalizes_offsetless_value_to_utc():
    # An ISO-8601 value with no offset parses to a NAIVE datetime; left naive it
    # would crash the tz-aware comparison in merge_items (outside safe_fetch),
    # taking down the whole poll. It must be treated as UTC.
    got = parse_iso8601_utc("2026-06-09T11:00:00")
    assert got.tzinfo is not None
    assert got == datetime(2026, 6, 9, 11, 0, tzinfo=timezone.utc)


def test_parse_iso8601_utc_keeps_trailing_z_as_utc():
    got = parse_iso8601_utc("2026-06-09T11:00:00Z")
    assert got == datetime(2026, 6, 9, 11, 0, tzinfo=timezone.utc)


def test_parse_iso8601_utc_preserves_explicit_offset():
    got = parse_iso8601_utc("2026-06-09T11:00:00+02:00")
    assert got.astimezone(timezone.utc) == datetime(2026, 6, 9, 9, 0, tzinfo=timezone.utc)


def test_clean_text_strips_ansi_and_control_escapes():
    # Raw ESC/BEL bytes from hostile federated content must never reach the
    # terminal; they are removed (replaced with a space) so words don't fuse.
    assert "\x1b" not in clean_text("hi\x1b[31mRED\x1b[0m there")
    assert "\x07" not in clean_text("ding\x07dong")
    assert clean_text("a\x1b[2J\x1b[Hb")  # screen-clear sequence: no crash, no ESC


def test_clean_text_strips_bidi_override_chars():
    # U+202E (RTL override) visually reverses/spoofs a headline.
    assert "‮" not in clean_text("safe‮txet det_kcatta")
    assert "⁦" not in clean_text("a⁦b⁩c")


def test_clean_text_collapses_whitespace():
    assert clean_text("a   b\n\nc\td") == "a b c d"


def test_clean_text_truncates_to_max_len_with_ellipsis():
    out = clean_text("x" * 100, max_len=10)
    assert len(out) == 10
    assert out.endswith("…")
