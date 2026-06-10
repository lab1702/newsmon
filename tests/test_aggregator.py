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


def test_seen_tracker_empty_first_poll_does_not_set_baseline():
    # An empty first poll (e.g. started offline) must not baseline against nothing,
    # else the next successful poll would flag every item as new.
    tracker = SeenTracker()
    assert tracker.mark_new([]) == []
    new = tracker.mark_new([_item("https://a.com/1", 1), _item("https://a.com/2", 2)])
    assert new == []  # this is the real baseline


def test_seen_tracker_caps_memory_with_oldest_eviction():
    tracker = SeenTracker(max_keys=2)
    tracker.mark_new([_item("https://a.com/1", 1)])  # baseline; seen={1}
    tracker.mark_new([_item("https://a.com/2", 1)])  # seen={1,2}
    tracker.mark_new([_item("https://a.com/3", 1)])  # over cap → evict oldest (1)
    assert len(tracker._seen) == 2
    # key 1 was evicted, so it now looks new again; key 3 is still remembered
    new = tracker.mark_new([_item("https://a.com/1", 1), _item("https://a.com/3", 1)])
    assert [i.url for i in new] == ["https://a.com/1"]


def test_seen_tracker_evicts_oldest_within_a_single_poll():
    # merge_items delivers a poll newest-first. When a single poll exceeds the
    # cap, eviction must drop the OLDEST keys (which leave the recency window
    # first), keeping the newest — otherwise the still-in-window newest items are
    # re-flagged 'new' on every poll and ring the bell endlessly.
    tracker = SeenTracker(max_keys=2)
    newest_first = [
        _item("https://a.com/3", 1),
        _item("https://a.com/2", 5),
        _item("https://a.com/1", 9),
    ]
    tracker.mark_new(newest_first)  # baseline; cap=2 must keep the 2 newest (3, 2)
    # the two newest are still remembered → presenting them again flags nothing
    new = tracker.mark_new(
        [_item("https://a.com/3", 1), _item("https://a.com/2", 5)]
    )
    assert new == []


def test_merge_survives_poisoned_items_without_aborting_the_whole_poll():
    # merge_items runs OUTSIDE safe_fetch: a single malformed scalar that slipped
    # past a parser must not crash the merge and discard every source's results.
    good = _item("https://good.com/1", 1, "web")
    bad_url = NewsItem("hn", "t", 123, NOW)  # non-string url
    bad_ipv6 = NewsItem("bing", "t", "http://[::1/bad", NOW)  # malformed IPv6
    results = [
        SourceResult("web", [good], Health.OK),
        SourceResult("hn", [bad_url], Health.OK),
        SourceResult("bing", [bad_ipv6], Health.OK),
    ]
    merged = merge_items(results, NOW - timedelta(hours=6))
    # The good item plus both poisoned items survive (distinct fallback keys);
    # crucially, nothing raised.
    assert len(merged) == 3
    assert good in merged


def test_seen_tracker_survives_poisoned_items():
    tracker = SeenTracker()
    bad_url = NewsItem("hn", "t", 123, NOW)
    bad_ipv6 = NewsItem("bing", "t2", "http://[::1/bad", NOW)
    # mark_new also evaluates dedup_key outside safe_fetch; must not raise.
    assert tracker.mark_new([bad_url, bad_ipv6]) == []  # baseline poll


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
