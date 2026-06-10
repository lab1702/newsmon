from datetime import timezone

from newsmon.sources.reddit import parse_reddit


def test_parse_reddit(fixtures_dir):
    text = (fixtures_dir / "reddit.json").read_text()
    items = parse_reddit(text)
    assert len(items) == 1
    item = items[0]
    assert item.source == "reddit"
    assert item.url == "https://www.reddit.com/r/news/comments/abc/quake_felt/"
    assert item.extra["subreddit"] == "news"
    assert item.extra["comments"] == 128
    assert item.published.tzinfo is not None


def test_parse_reddit_null_data_returns_no_items():
    # A present-but-null "data" key must not crash the parser
    assert parse_reddit('{"data": null}') == []


def test_parse_reddit_wrong_type_data_returns_no_items():
    # Truthy-but-wrong-type containers must coerce to empty, not crash.
    assert parse_reddit('{"data": "error"}') == []
    assert parse_reddit('{"data": {"children": "nope"}}') == []
    assert parse_reddit('{"data": {"children": ["x", null]}}') == []


def test_parse_reddit_epoch_zero_is_kept_not_restamped_to_now():
    # created_utc == 0 is a valid Unix epoch (1970), but is falsy; it must be
    # converted, not mistaken for "missing" and stamped with the current time.
    text = (
        '{"data": {"children": [{"data":'
        ' {"title": "t", "permalink": "/r/x/1/", "created_utc": 0}}]}}'
    )
    items = parse_reddit(text)
    assert items[0].published.astimezone(timezone.utc).year == 1970


def test_parse_reddit_null_title_falls_back_to_placeholder():
    text = '{"data": {"children": [{"data": {"title": null, "permalink": "/r/x/1/"}}]}}'
    items = parse_reddit(text)
    assert items[0].title == "(untitled)"


def test_parse_reddit_bad_timestamp_does_not_lose_batch():
    # A non-numeric created_utc must fall back to now(), not raise away the batch.
    text = (
        '{"data": {"children": [{"data":'
        ' {"title": "t", "permalink": "/r/x/1/", "created_utc": "oops"}}]}}'
    )
    items = parse_reddit(text)
    assert len(items) == 1
    assert items[0].published.tzinfo is not None
