from datetime import datetime, timedelta, timezone

from newsmon.aggregator import SeenTracker, merge_items, poll_sources
from newsmon.health import Health, SourceResult
from newsmon.models import NewsItem

NOW = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)


def _item(url, minutes_ago, source="web"):
    return NewsItem(
        source=source,
        title=url,
        url=url,
        published=NOW - timedelta(minutes=minutes_ago),
    )


def test_source_result_defaults():
    r = SourceResult(name="web", items=[], health=Health.OK)
    assert r.error is None
    assert r.elapsed == 0.0
    assert r.count == 0


def test_count_reflects_items():
    items = [_item("https://a.com/1", 1), _item("https://a.com/2", 2)]
    r = SourceResult(name="web", items=items, health=Health.OK)
    assert r.count == 2


def test_merge_filters_old_dedups_and_sorts_newest_first():
    results = [
        SourceResult("web", [_item("https://a.com/1", 10), _item("https://a.com/2", 600)], Health.OK),
        SourceResult("hn", [_item("https://a.com/1?utm_source=hn", 5, "hn"), _item("https://b.com/3", 1, "hn")], Health.OK),
    ]
    since = NOW - timedelta(hours=6)
    merged = merge_items(results, since)
    urls = [i.url for i in merged]
    # b.com/3 (1m) newest, then a.com/1 (kept first occurrence, 10m), a.com/2 dropped (10h old)
    assert urls == ["https://b.com/3", "https://a.com/1"]


def test_merge_handles_empty():
    assert merge_items([], NOW) == []


def test_seen_tracker_first_poll_marks_nothing_new():
    tracker = SeenTracker()
    items = [_item("https://a.com/1", 1), _item("https://a.com/2", 2)]
    new = tracker.mark_new(items)
    assert new == []  # first poll is the baseline


def test_seen_tracker_reports_only_unseen_after_baseline():
    tracker = SeenTracker()
    tracker.mark_new([_item("https://a.com/1", 1)])
    new = tracker.mark_new([_item("https://a.com/2", 0), _item("https://a.com/1", 1)])
    assert [i.url for i in new] == ["https://a.com/2"]


class _Src:
    def __init__(self, name, items):
        self.name = name
        self._items = items

    async def fetch(self, client, topic, since):
        return self._items


async def test_poll_sources_returns_result_per_source():
    sources = [
        _Src("web", [_item("https://a.com/1", 1)]),
        _Src("hn", [_item("https://b.com/2", 2, "hn")]),
    ]
    results = await poll_sources(sources, None, "quake", NOW, timeout=2, slow_after=10)
    assert {r.name for r in results} == {"web", "hn"}
    assert all(r.health is Health.OK for r in results)
