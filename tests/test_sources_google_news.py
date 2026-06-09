from datetime import timezone

from newsmon.sources.google_news import parse_google_news


def test_parse_google_news(fixtures_dir):
    text = (fixtures_dir / "google_news.xml").read_text()
    items = parse_google_news(text)
    assert len(items) == 2
    first = items[0]
    assert first.source == "web"
    assert first.title == "Major quake strikes coast - Example News"
    assert first.url == "https://news.google.com/rss/articles/abc?oc=5"
    assert first.published.tzinfo is not None
    assert first.published.astimezone(timezone.utc).hour == 11
    assert first.extra.get("outlet") == "Example News"
