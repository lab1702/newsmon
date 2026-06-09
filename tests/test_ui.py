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
