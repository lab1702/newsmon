from datetime import datetime, timezone

from conftest import FakeStreamClient

from newsmon.sources.bing import BingNewsSource, _unwrap, parse_bing_news


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


def test_unwrap_returns_real_article_url():
    link = "https://www.bing.com/news/apiclick.aspx?url=https%3a%2f%2fe.com%2fa"
    assert _unwrap(link) == "https://e.com/a"


def test_unwrap_malformed_ipv6_does_not_crash():
    # An unterminated IPv6 literal in the url param made urlsplit raise ValueError
    # later in dedup_key, taking down the whole poll. _unwrap must neutralize it.
    link = "http://www.bing.com/news/apiclick.aspx?url=http%3a%2f%2f%5b%3a%3a1%2fbad"
    assert _unwrap(link) == ""


def test_unwrap_rejects_non_http_schemes():
    for scheme in ("mailto%3ax%40y.com", "data%3atext%2fhtml%2cx", "notaurl"):
        link = f"https://www.bing.com/news/apiclick.aspx?url={scheme}"
        assert _unwrap(link) == ""


def test_unwrap_falls_back_to_valid_link_without_url_param():
    assert _unwrap("https://www.bing.com/article") == "https://www.bing.com/article"


async def test_fetch_requests_rss(fixtures_dir):
    text = (fixtures_dir / "bing_news.xml").read_text()
    client = FakeStreamClient(text)
    since = datetime(2026, 6, 9, 6, 0, tzinfo=timezone.utc)
    items = await BingNewsSource().fetch(client, "quake", since)
    assert len(items) == 2
    _, _, kwargs = client.calls[0]
    assert kwargs["params"]["q"] == "quake"
    assert kwargs["params"]["format"] == "rss"
