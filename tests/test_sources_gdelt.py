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


def test_parse_gdelt_wrong_type_articles_returns_no_items():
    # A truthy-but-wrong-type "articles" (e.g. an upstream error page) must not
    # be iterated as a string and crash the parser.
    assert parse_gdelt('{"articles": "error"}') == []
    assert parse_gdelt('{"articles": 123}') == []


def test_parse_gdelt_non_dict_article_is_skipped():
    # A non-dict element in the articles list must be skipped, not crashed on.
    assert parse_gdelt('{"articles": ["x", null, 5]}') == []


def test_parse_gdelt_non_string_seendate_is_skipped():
    # A truthy non-string seendate (JSON number) reaches strptime and raises
    # TypeError — not the caught ValueError. Skip the record, keep the batch.
    text = '{"articles": [{"seendate": 20260609, "title": "t", "url": "https://e/a"}]}'
    assert parse_gdelt(text) == []


def test_parse_gdelt_non_string_url_becomes_empty():
    text = (
        '{"articles": [{"seendate": "20260609T113000Z", "title": "t", "url": 123}]}'
    )
    items = parse_gdelt(text)
    assert items[0].url == ""


def test_parse_gdelt_non_string_title_uses_placeholder():
    text = (
        '{"articles": [{"seendate": "20260609T113000Z", "title": 5,'
        ' "url": "https://e/a"}]}'
    )
    items = parse_gdelt(text)
    assert items[0].title == "(untitled)"


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
