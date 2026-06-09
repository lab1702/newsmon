from newsmon.sources.hackernews import parse_hackernews


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
