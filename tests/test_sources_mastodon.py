from datetime import datetime, timezone

from conftest import FakeStreamClient

from newsmon.sources.mastodon import MastodonSource, _text, parse_mastodon


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


def test_text_strips_ansi_escapes_from_post_body():
    # The hashtag feed aggregates federated posts; the HTML body is fully
    # attacker-controlled and must not carry raw ANSI/BEL escapes to the terminal.
    out = _text("hi\x1b[31mRED\x1b[0m <b>there</b>\x07")
    assert "\x1b" not in out
    assert "\x07" not in out
    assert "there" in out


def test_text_strips_bidi_override_from_post_body():
    out = _text("safe‮spoofed")
    assert "‮" not in out


def test_parse_mastodon_survives_malformed_link():
    # The hashtag feed aggregates untrusted federated instances. One post with a
    # malformed authority (unterminated IPv6 literal) must not raise out of
    # _author/urlsplit and discard every legitimate post in the feed.
    feed = (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
        "<item><title>t</title><link>https://masto.ai/@alice/1</link>"
        "<description>good</description></item>"
        "<item><title>t</title><link>http://[oops</link>"
        "<description>bad</description></item>"
        "</channel></rss>"
    )
    items = parse_mastodon(feed)
    assert len(items) == 2
    assert items[0].extra["author"] == "@alice@masto.ai"
    assert items[1].extra["author"] == ""  # malformed link degrades to no author


async def test_fetch_builds_hashtag_from_topic(fixtures_dir):
    text = (fixtures_dir / "mastodon.xml").read_text()
    client = FakeStreamClient(text)
    since = datetime(2026, 6, 9, 6, 0, tzinfo=timezone.utc)
    items = await MastodonSource().fetch(client, "Los Angeles", since)
    assert len(items) == 2
    _, url, _ = client.calls[0]
    # multi-word topics collapse to a single lowercase hashtag feed
    assert url.endswith("/tags/losangeles.rss")


async def test_fetch_empty_tag_skips_request():
    client = FakeStreamClient("")
    since = datetime(2026, 6, 9, 6, 0, tzinfo=timezone.utc)
    items = await MastodonSource().fetch(client, "!!!", since)
    assert items == []
    assert client.calls == []
