import pytest

from newsmon.sources.twitter import normalize_to_x_url, parse_nitter


def test_parse_nitter(fixtures_dir):
    text = (fixtures_dir / "nitter.xml").read_text()
    items = parse_nitter(text)
    assert len(items) == 1
    item = items[0]
    assert item.source == "x"
    assert item.url == "https://x.com/user/status/1234"
    assert item.title == "BREAKING: quake felt downtown"
    assert item.extra["author"] == "@user"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://nitter.net/user/status/1234#m", "https://x.com/user/status/1234"),
        ("https://nitter.example/a/status/9?x=1", "https://x.com/a/status/9"),
    ],
)
def test_normalize_to_x_url(raw, expected):
    assert normalize_to_x_url(raw) == expected
