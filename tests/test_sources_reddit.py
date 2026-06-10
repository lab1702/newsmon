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


def test_parse_reddit_boolean_created_utc_is_not_treated_as_epoch():
    # A JSON boolean is an int subclass; true would parse to epoch 1 (1970) and
    # the item would be silently dropped by the recency filter. Treat as missing.
    text = (
        '{"data": {"children": [{"data":'
        ' {"title": "t", "permalink": "/r/x/1/", "created_utc": true}}]}}'
    )
    items = parse_reddit(text)
    assert items[0].published.astimezone(timezone.utc).year != 1970


def test_parse_reddit_non_string_permalink_does_not_build_corrupt_url():
    # A truthy non-string permalink must not be concatenated into the URL.
    text = (
        '{"data": {"children": [{"data":'
        ' {"title": "t", "permalink": 123, "url": "https://e.com/a"}}]}}'
    )
    items = parse_reddit(text)
    assert items[0].url == "https://e.com/a"


def test_parse_reddit_non_string_url_fallback_becomes_empty():
    text = (
        '{"data": {"children": [{"data": {"title": "t", "url": 999}}]}}'
    )
    items = parse_reddit(text)
    assert items[0].url == ""


def test_parse_reddit_at_permalink_is_not_an_open_redirect():
    # permalink "@evil.com/x" would yield www.reddit.com@evil.com (host evil.com).
    # It doesn't start with "/", so it must fall back, not build that URL.
    text = (
        '{"data": {"children": [{"data":'
        ' {"title": "t", "permalink": "@evil.com/x", "url": ""}}]}}'
    )
    items = parse_reddit(text)
    assert "evil.com" not in items[0].url


def test_parse_reddit_non_string_title_uses_placeholder():
    text = (
        '{"data": {"children": [{"data": {"title": 42, "permalink": "/r/x/1/"}}]}}'
    )
    items = parse_reddit(text)
    assert items[0].title == "(untitled)"
