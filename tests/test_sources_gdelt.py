from datetime import datetime, timezone

from conftest import FakeStreamClient

from newsmon.sources.gdelt import GdeltSource, parse_gdelt


def test_parse_gdelt(fixtures_dir):
    text = (fixtures_dir / "gdelt.json").read_text()
    items = parse_gdelt(text)
    assert len(items) == 2
    first = items[0]
    assert first.source == "gdelt"
    assert first.title == "Major quake strikes coast"
    assert first.url == "https://example.com/quake-tool"
    assert first.published.tzinfo is not None
    assert first.published.astimezone(timezone.utc).hour == 11
    assert first.extra.get("domain") == "example.com"
    assert first.extra.get("country") == "United States"


def test_parse_gdelt_empty_returns_no_items():
    # GDELT omits the "articles" key entirely when nothing matches
    assert parse_gdelt("{}") == []


def test_parse_gdelt_null_articles_returns_no_items():
    # A present-but-null key must not crash the parser
    assert parse_gdelt('{"articles": null}') == []


async def test_fetch_sorts_newest_first(fixtures_dir):
    text = (fixtures_dir / "gdelt.json").read_text()
    client = FakeStreamClient(text)
    since = datetime(2026, 6, 9, 6, 0, tzinfo=timezone.utc)
    await GdeltSource().fetch(client, "quake", since)
    _, _, kwargs = client.calls[0]
    params = kwargs["params"]
    assert params["query"] == "quake"
    assert params["mode"] == "artlist"
    assert params["format"] == "json"
    assert params["sort"] == "datedesc"
