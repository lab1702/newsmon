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
