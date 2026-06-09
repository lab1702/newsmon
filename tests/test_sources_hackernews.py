from datetime import datetime, timezone

from newsmon.sources.hackernews import HackerNewsSource, parse_hackernews


class _FakeResp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class _FakeClient:
    def __init__(self, text):
        self.text = text
        self.calls = []

    async def get(self, url, params=None, headers=None):
        self.calls.append((url, params, headers))
        return _FakeResp(self.text)


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


async def test_fetch_filters_by_since(fixtures_dir):
    text = (fixtures_dir / "hackernews.json").read_text()
    client = _FakeClient(text)
    since = datetime(2026, 6, 9, 6, 0, tzinfo=timezone.utc)
    items = await HackerNewsSource().fetch(client, "quake", since)
    assert len(items) == 2  # parser still runs on the response
    _, params, _ = client.calls[0]
    assert params["numericFilters"] == f"created_at_i>{int(since.timestamp())}"
