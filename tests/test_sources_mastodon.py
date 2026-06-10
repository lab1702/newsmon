from datetime import datetime, timezone

from newsmon.sources.mastodon import MastodonSource, parse_mastodon


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


def test_parse_mastodon(fixtures_dir):
    text = (fixtures_dir / "mastodon.xml").read_text()
    items = parse_mastodon(text)
    assert len(items) == 2
    first = items[0]
    assert first.source == "masto"
    assert first.url == "https://masto.ai/@emsc/116723066958008109"
    # title derived from the HTML post body: tags stripped, entities unescaped
    assert first.title == "M 4.6 earthquake detected near the coast #earthquake"
    assert first.published.tzinfo is not None
    assert first.published.astimezone(timezone.utc).hour == 11
    # author reconstructed as @handle@instance from the post URL
    assert first.extra.get("author") == "@emsc@masto.ai"
    assert items[1].extra.get("author") == "@earthquake_monitor@mstdn.social"


async def test_fetch_builds_hashtag_from_topic(fixtures_dir):
    text = (fixtures_dir / "mastodon.xml").read_text()
    client = _FakeClient(text)
    since = datetime(2026, 6, 9, 6, 0, tzinfo=timezone.utc)
    items = await MastodonSource().fetch(client, "Los Angeles", since)
    assert len(items) == 2
    url, _, _ = client.calls[0]
    # multi-word topics collapse to a single lowercase hashtag feed
    assert url.endswith("/tags/losangeles.rss")


async def test_fetch_empty_tag_skips_request():
    client = _FakeClient("")
    since = datetime(2026, 6, 9, 6, 0, tzinfo=timezone.utc)
    items = await MastodonSource().fetch(client, "!!!", since)
    assert items == []
    assert client.calls == []
