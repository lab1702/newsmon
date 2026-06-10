from datetime import datetime, timedelta, timezone

from newsmon.sources.youtube import (
    _extract_initial_data,
    parse_relative_time,
    parse_youtube,
)

NOW = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)


def test_parse_relative_time_hours():
    assert parse_relative_time("2 hours ago", NOW) == NOW - timedelta(hours=2)


def test_parse_relative_time_streamed_prefix():
    assert parse_relative_time("Streamed 30 minutes ago", NOW) == NOW - timedelta(minutes=30)


def test_parse_relative_time_unparseable():
    assert parse_relative_time("", NOW) is None


def test_parse_relative_time_huge_quantity_is_unparseable():
    # An absurd digit run overflows timedelta; treat as unparseable, don't raise.
    assert parse_relative_time("9" * 400 + " years ago", NOW) is None


def test_parse_youtube_joins_multi_run_title():
    html = (
        'ytInitialData = {"videoRenderer": {"videoId": "v1",'
        ' "publishedTimeText": {"simpleText": "1 hour ago"},'
        ' "title": {"runs": [{"text": "Break"}, {"text": "ing news"}]}}};</script>'
    )
    items = parse_youtube(html, NOW)
    assert items[0].title == "Breaking news"


def test_parse_youtube_handles_deeply_nested_data():
    # A pathologically nested payload must not blow the recursion limit; the
    # walker is iterative, so this returns cleanly (no videoRenderers → []).
    depth = 5000
    html = "ytInitialData = " + "[" * depth + "]" * depth + ";</script>"
    assert parse_youtube(html, NOW) == []


def test_parse_youtube(fixtures_dir):
    html = (fixtures_dir / "youtube.html").read_text()
    items = parse_youtube(html, NOW)
    assert len(items) == 2
    first = items[0]
    assert first.source == "youtube"
    assert first.url == "https://www.youtube.com/watch?v=vid123"
    assert first.title == "LIVE: quake coverage"
    assert first.published == NOW - timedelta(hours=2)
    assert first.extra["channel"] == "News Channel"
    # the 3-years-ago video is parsed with an old timestamp (window drops it later)
    assert items[1].published < NOW - timedelta(days=365)


def test_extract_initial_data_ignores_trailing_script():
    # The assignment is followed by more JS before </script>; the brace-balanced
    # scan must stop at the object's own closing brace, not run to end-of-script.
    html = 'var x=1;ytInitialData = {"a": {"b": "}}; not json"}};\nmore();</script>'
    assert _extract_initial_data(html) == '{"a": {"b": "}}; not json"}}'


def test_extract_initial_data_absent():
    assert _extract_initial_data("<html>no data here</html>") is None


def test_parse_youtube_encodes_video_id_in_url():
    # A corrupted/hostile videoId must be percent-encoded so it can't inject
    # extra query params into the watch URL.
    html = (
        'ytInitialData = {"videoRenderer": {"videoId": "abc&t=100",'
        ' "publishedTimeText": {"simpleText": "1 hour ago"},'
        ' "title": {"runs": [{"text": "t"}]}}};</script>'
    )
    items = parse_youtube(html, NOW)
    assert items[0].url == "https://www.youtube.com/watch?v=abc%26t%3D100"


def test_parse_youtube_skips_renderer_missing_run_text():
    # A title run without a "text" key must drop only that video, not abort all.
    html = (
        'ytInitialData = {"videoRenderer": {"videoId": "v1",'
        ' "publishedTimeText": {"simpleText": "1 hour ago"},'
        ' "title": {"runs": [{}]}}};</script>'
    )
    items = parse_youtube(html, NOW)
    assert len(items) == 1
    assert items[0].title == ""
    assert items[0].url == "https://www.youtube.com/watch?v=v1"
