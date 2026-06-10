from datetime import datetime, timezone

from conftest import FakeStreamClient

from newsmon.sources.bing import BingNewsSource, parse_bing_news


def test_parse_bing_news(fixtures_dir):
    text = (fixtures_dir / "bing_news.xml").read_text()
    items = parse_bing_news(text)
    assert len(items) == 2
    first = items[0]
    assert first.source == "bing"
    assert first.title == "Major quake strikes coast"
    # the apiclick redirect is unwrapped to the real article URL
    assert first.url == "https://example.com/quake-coast"
    assert first.published.tzinfo is not None
    assert first.published.astimezone(timezone.utc).hour == 11
    assert first.extra.get("outlet") == "Example News"


async def test_fetch_requests_rss(fixtures_dir):
    text = (fixtures_dir / "bing_news.xml").read_text()
    client = FakeStreamClient(text)
    since = datetime(2026, 6, 9, 6, 0, tzinfo=timezone.utc)
    items = await BingNewsSource().fetch(client, "quake", since)
    assert len(items) == 2
    _, _, kwargs = client.calls[0]
    assert kwargs["params"]["q"] == "quake"
    assert kwargs["params"]["format"] == "rss"
