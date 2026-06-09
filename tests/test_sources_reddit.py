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
