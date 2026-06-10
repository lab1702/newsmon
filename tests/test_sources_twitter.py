from datetime import datetime, timezone

import pytest
from conftest import FakeStreamClient

from newsmon.sources.twitter import (
    TwitterSource,
    normalize_to_x_url,
    parse_nitter,
)


def test_parse_nitter(fixtures_dir):
    text = (fixtures_dir / "nitter.xml").read_text()
    items = parse_nitter(text)
    assert len(items) == 1
    item = items[0]
    assert item.source == "x"
    assert item.url == "https://x.com/user/status/1234"
    assert item.title == "BREAKING: quake felt downtown"
    assert item.extra["author"] == "@user"


def _nitter_rss(title: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        f"<item><title>{title}</title>"
        "<link>https://nitter.net/u/status/1</link></item>"
        "</channel></rss>"
    )


def test_parse_nitter_strips_bidi_override_from_title():
    # A hostile Nitter instance controls the title; a U+202E override visually
    # spoofs the headline and must be stripped.
    items = parse_nitter(_nitter_rss("safe‮spoofed"))
    assert "‮" not in items[0].title


def test_parse_nitter_truncates_overlong_title():
    items = parse_nitter(_nitter_rss("x" * 1000))
    assert len(items[0].title) <= 500


async def test_fetch_disables_redirects_for_untrusted_instances(fixtures_dir):
    # Nitter instances are untrusted third parties; following their redirects
    # turns the shared client into a blind-SSRF vector (e.g. a 302 to
    # 169.254.169.254). The fetch must opt out of redirect-following.
    text = (fixtures_dir / "nitter.xml").read_text()
    client = FakeStreamClient(text)
    since = datetime(2026, 6, 9, 6, 0, tzinfo=timezone.utc)
    await TwitterSource().fetch(client, "quake", since)
    _, _, kwargs = client.calls[0]
    assert kwargs.get("follow_redirects") is False


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://nitter.net/user/status/1234#m", "https://x.com/user/status/1234"),
        ("https://nitter.example/a/status/9?x=1", "https://x.com/a/status/9"),
        # missing/host-only links have no path to map and must not fabricate a URL
        ("", ""),
        ("https://nitter.net/", ""),
    ],
)
def test_normalize_to_x_url(raw, expected):
    assert normalize_to_x_url(raw) == expected
