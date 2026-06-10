from datetime import datetime, timedelta, timezone

import pytest

from newsmon.health import Health, SourceResult
from newsmon.models import NewsItem
from newsmon.ui import format_row, is_browsable_url, render_sidebar

NOW = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)


def test_format_row_uses_source_name():
    item = NewsItem("web", "Quake hits coast", "https://a/1",
                    datetime(2026, 6, 9, 11, 30, tzinfo=timezone.utc))
    source, when, title = format_row(item, tz=timezone.utc, now=NOW)
    # the stream's leading column shows the source name, matching the sidebar
    assert source == "web"
    assert when == "11:30"  # same day as `now` → time only
    assert title == "Quake hits coast"


def test_format_row_prefixes_date_for_other_days():
    # With a multi-day window, an item from a different day must carry its date
    # so same-time items on different days don't render identically.
    item = NewsItem("web", "Older quake", "https://a/2",
                    datetime(2026, 6, 7, 11, 30, tzinfo=timezone.utc))
    _, when, _ = format_row(item, tz=timezone.utc, now=NOW)
    assert when == "06-07 11:30"


def test_format_row_sanitizes_title_escapes_and_bidi():
    # The title is untrusted feed text and format_row is the single choke point
    # before it reaches the terminal via Text(). Raw ANSI/control escapes and
    # bidi-override chars must be stripped here so no parser can forget to.
    item = NewsItem("web", "Quake\x1b[2J\x1b]0;pwned\x07 ‮gnp", "https://a/1",
                    datetime(2026, 6, 9, 11, 30, tzinfo=timezone.utc))
    _, _, title = format_row(item, tz=timezone.utc, now=NOW)
    assert "\x1b" not in title
    assert "\x07" not in title
    assert "‮" not in title


def test_format_row_survives_out_of_range_timestamp():
    # A far-future timestamp (e.g. from a hostile feed) overflows astimezone()
    # for a user east of UTC. format_row runs in the shared render loop outside
    # safe_fetch, so it must degrade rather than crash the whole TUI.
    east = timezone(timedelta(hours=9))
    item = NewsItem("gdelt", "Boom", "https://a/1",
                    datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
    source, when, title = format_row(item, tz=east, now=NOW)
    assert source == "gdelt"
    assert title == "Boom"
    assert when  # some non-empty timestamp string, no exception


def test_render_sidebar_shows_health_and_counts():
    results = [
        SourceResult("web", [object()], Health.OK),
        SourceResult("x", [], Health.FAILED, error="boom"),
    ]
    text = render_sidebar(results, new_count=3)
    assert "3 new" in text
    assert "web" in text and "x" in text
    assert "✅" in text and "❌" in text


def test_render_sidebar_numbers_each_source():
    results = [
        SourceResult("web", [object()], Health.OK),
        SourceResult("hn", [], Health.OK),
    ]
    text = render_sidebar(results, new_count=0, enabled={"web", "hn"})
    # each source is prefixed with its 1-based toggle key
    assert "1 " in text and "web" in text
    assert "2 " in text and "hn" in text
    # nothing disabled → no dim markup
    assert "[dim]" not in text


def test_render_sidebar_dims_disabled_source():
    results = [
        SourceResult("web", [object()], Health.OK),
        SourceResult("x", [object()], Health.OK),
    ]
    text = render_sidebar(results, new_count=0, enabled={"web"})
    lines = text.splitlines()
    web_line = next(line for line in lines if "web" in line)
    x_line = next(line for line in lines if "x " in line and "web" not in line)
    # enabled source is rendered plainly; disabled one is dimmed and marked off
    assert "[dim]" not in web_line
    assert "[dim]" in x_line and "off" in x_line


@pytest.mark.parametrize(
    "url,ok",
    [
        ("https://example.com/a", True),
        ("http://example.com", True),
        ("file:///etc/passwd", False),
        ("javascript:alert(1)", False),
        ("", False),
        ("https://", False),
        ("ftp://example.com/x", False),
        # urlsplit strips these silently, so they must be rejected before the
        # raw string reaches webbrowser.open / the clipboard (paste-injection).
        ("http://example.com/\nrm -rf ~", False),
        ("http://example.com/\twhoami", False),
        ("http://example.com/\rfoo", False),
    ],
)
def test_is_browsable_url(url, ok):
    assert is_browsable_url(url) is ok


def test_render_sidebar_omits_toggle_number_past_ninth():
    # Only the first 9 sources get a digit toggle key; a 10th is shown without
    # an (unpressable) number.
    results = [SourceResult(f"s{i}", [], Health.OK) for i in range(1, 11)]
    text = render_sidebar(results, new_count=0)
    lines = text.splitlines()
    assert lines[2].startswith("1 ")   # first source numbered
    assert lines[10].startswith("9 ")  # ninth source numbered
    assert lines[11].startswith("  ")  # tenth source: blank toggle slot, no "10"
    assert "s10" in lines[11]
