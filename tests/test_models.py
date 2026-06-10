from datetime import datetime, timezone

from newsmon.models import NewsItem


def _item(url: str) -> NewsItem:
    return NewsItem(
        source="web",
        title="Quake hits coast",
        url=url,
        published=datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc),
    )


def test_defaults_are_empty():
    item = _item("https://example.com/a")
    assert item.summary == ""
    assert item.extra == {}


def test_dedup_key_ignores_scheme_case_fragment_and_tracking_params():
    a = _item("https://Example.com/Story?utm_source=x&id=7#frag")
    b = _item("http://example.com/Story?id=7")
    assert a.dedup_key == b.dedup_key


def test_dedup_key_keeps_meaningful_query_and_path():
    a = _item("https://example.com/story?id=7")
    b = _item("https://example.com/story?id=8")
    assert a.dedup_key != b.dedup_key


def test_dedup_key_survives_non_string_url():
    # A non-string url that slipped past a parser must not crash dedup_key, which
    # runs in merge_items OUTSIDE safe_fetch — one bad item would otherwise wipe
    # the whole poll for every source. Each yields a usable, hashable string key.
    for bad in (123, ["x"], {"a": 1}, None):
        item = NewsItem(
            source="hn",
            title="t",
            url=bad,  # type: ignore[arg-type]
            published=datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc),
        )
        key = item.dedup_key
        assert isinstance(key, str)
        hash(key)  # must be hashable for the seen-set


def test_dedup_key_survives_malformed_ipv6_url():
    # An unterminated IPv6 literal makes urlsplit raise ValueError; it must be
    # swallowed rather than aborting merge_items.
    item = _item("http://[::1/bad")
    assert isinstance(item.dedup_key, str)
