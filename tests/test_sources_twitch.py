from newsmon.sources.twitch import parse_twitch


def test_parse_twitch_only_live(fixtures_dir):
    text = (fixtures_dir / "twitch.json").read_text()
    items = parse_twitch(text)
    assert len(items) == 1  # offline channel excluded
    item = items[0]
    assert item.source == "twitch"
    assert item.url == "https://twitch.tv/newsnow"
    assert item.title == "Live quake coverage"
    assert item.extra["viewers"] == 5400
    assert item.published.hour == 11
