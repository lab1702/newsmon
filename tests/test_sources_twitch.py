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


def test_parse_twitch_null_search_returns_no_items():
    # A present-but-null "searchFor" key must not crash the parser
    assert parse_twitch('{"data": {"searchFor": null}}') == []


def test_parse_twitch_wrong_type_containers_return_no_items():
    # Truthy-but-wrong-type nodes anywhere in the chain must coerce, not crash.
    assert parse_twitch('{"data": "error"}') == []
    assert parse_twitch('{"data": {"searchFor": "x"}}') == []
    assert parse_twitch('{"data": {"searchFor": {"channels": "x"}}}') == []
    assert parse_twitch('{"data": {"searchFor": {"channels": {"edges": "x"}}}}') == []


def test_parse_twitch_wrong_type_stream_is_skipped():
    # A truthy-but-wrong-type "stream" must be skipped like an offline channel.
    text = (
        '{"data": {"searchFor": {"channels": {"edges": [{"item":'
        ' {"login": "x", "stream": "live"}}]}}}}'
    )
    assert parse_twitch(text) == []


def test_parse_twitch_non_string_created_at_is_skipped():
    # A non-string createdAt reaches parse_iso8601_utc and raises AttributeError,
    # not the caught ValueError; the edge must be skipped without aborting the loop.
    text = (
        '{"data": {"searchFor": {"channels": {"edges": [{"item":'
        ' {"login": "x", "stream": {"createdAt": 123, "viewersCount": 1}}}]}}}}'
    )
    assert parse_twitch(text) == []


def test_parse_twitch_non_string_login_is_skipped():
    # A non-string login reaches quote() and raises TypeError; skip the edge.
    text = (
        '{"data": {"searchFor": {"channels": {"edges": [{"item":'
        ' {"login": 999, "stream": {"createdAt": "2026-06-09T11:00:00Z",'
        ' "viewersCount": 1}}}]}}}}'
    )
    assert parse_twitch(text) == []


def test_parse_twitch_one_bad_edge_does_not_drop_valid_channels():
    text = (
        '{"data": {"searchFor": {"channels": {"edges": ['
        '{"item": {"login": "good", "broadcastSettings": {"title": "Live"},'
        ' "stream": {"createdAt": "2026-06-09T11:00:00Z", "viewersCount": 1}}},'
        '{"item": {"login": 999, "stream": {"createdAt": "2026-06-09T11:00:00Z",'
        ' "viewersCount": 1}}}]}}}}'
    )
    items = parse_twitch(text)
    assert [i.url for i in items] == ["https://twitch.tv/good"]


def test_parse_twitch_non_string_title_is_coerced():
    # A non-string broadcastSettings.title would reach Text() and crash render.
    text = (
        '{"data": {"searchFor": {"channels": {"edges": [{"item":'
        ' {"login": "ch", "broadcastSettings": {"title": 999},'
        ' "stream": {"createdAt": "2026-06-09T11:00:00Z", "viewersCount": 1}}}]}}}}'
    )
    items = parse_twitch(text)
    assert isinstance(items[0].title, str)
    assert items[0].title == "ch"


def test_parse_twitch_encodes_login_in_url():
    # A corrupted/hostile login must be percent-encoded so it can't inject extra
    # path/query segments into the channel URL.
    text = (
        '{"data": {"searchFor": {"channels": {"edges": [{"item":'
        ' {"login": "user?utm=x", "displayName": "D",'
        ' "stream": {"createdAt": "2026-06-09T11:00:00Z", "viewersCount": 1}}}]}}}}'
    )
    items = parse_twitch(text)
    assert items[0].url == "https://twitch.tv/user%3Futm%3Dx"
