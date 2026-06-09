import pytest

from datetime import datetime, timezone

from newsmon.health import Health, SourceResult
from newsmon.models import NewsItem
from newsmon.ui import SOURCE_ICONS, format_row, render_sidebar

NOW = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)


def test_format_row():
    item = NewsItem("web", "Quake hits coast", "https://a/1",
                    datetime(2026, 6, 9, 11, 30, tzinfo=timezone.utc))
    icon, when, title = format_row(item, tz=timezone.utc)
    assert icon == SOURCE_ICONS["web"]
    assert when == "11:30"
    assert title == "Quake hits coast"


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


import pytest

from newsmon.ui import is_browsable_url


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
    ],
)
def test_is_browsable_url(url, ok):
    assert is_browsable_url(url) is ok
