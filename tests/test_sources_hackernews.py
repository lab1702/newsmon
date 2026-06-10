from datetime import datetime, timezone

from conftest import FakeStreamClient

from newsmon.sources.hackernews import HackerNewsSource, parse_hackernews


def test_parse_hackernews(fixtures_dir):
    text = (fixtures_dir / "hackernews.json").read_text()
    items = parse_hackernews(text)
    assert len(items) == 2
    assert items[0].source == "hn"
    assert items[0].url == "https://example.com/quake-tool"
    assert items[0].published.hour == 11
    assert items[0].extra["points"] == 42
    # null url falls back to the HN discussion permalink
    assert items[1].url == "https://news.ycombinator.com/item?id=222"


def test_parse_hackernews_null_hits_returns_no_items():
    # A present-but-null "hits" key must not crash the parser
    assert parse_hackernews('{"hits": null}') == []


def test_parse_hackernews_wrong_type_hits_returns_no_items():
    # A truthy-but-wrong-type "hits" must not be iterated as a string and crash.
    assert parse_hackernews('{"hits": "error"}') == []
    assert parse_hackernews('{"hits": 7}') == []


def test_parse_hackernews_non_dict_hit_is_skipped():
    assert parse_hackernews('{"hits": ["x", null]}') == []


def test_parse_hackernews_encodes_object_id_in_discussion_url():
    # A corrupted/hostile objectID must be percent-encoded so it can't inject
    # extra query params into the discussion URL.
    text = (
        '{"hits": [{"created_at": "2026-06-09T11:00:00Z", "title": "t",'
        ' "objectID": "123&sort=controversial"}]}'
    )
    items = parse_hackernews(text)
    assert items[0].extra["discussion"] == (
        "https://news.ycombinator.com/item?id=123%26sort%3Dcontroversial"
    )


async def test_fetch_filters_by_since(fixtures_dir):
    text = (fixtures_dir / "hackernews.json").read_text()
    client = FakeStreamClient(text)
    since = datetime(2026, 6, 9, 6, 0, tzinfo=timezone.utc)
    items = await HackerNewsSource().fetch(client, "quake", since)
    assert len(items) == 2  # parser still runs on the response
    _, _, kwargs = client.calls[0]
    assert kwargs["params"]["numericFilters"] == f"created_at_i>{int(since.timestamp())}"
