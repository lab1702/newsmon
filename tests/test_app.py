from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from newsmon.app import NewsmonApp
from newsmon.cli import Config
from newsmon.health import Health, SourceResult
from newsmon.models import NewsItem


def _one_result():
    item = NewsItem(
        "web", "Quake headline", "https://example.com/quake",
        datetime.now(timezone.utc),
    )
    return [SourceResult("web", [item], Health.OK)]


async def test_enter_opens_selected_item_in_browser():
    """Pressing Enter on the focused stream table opens the row's URL.

    The DataTable consumes the Enter key (emitting RowSelected), so this only
    works if the app handles that message rather than relying on an App-level
    'enter' binding that the focused table shadows.
    """
    poll = AsyncMock(return_value=_one_result())
    opened = MagicMock()
    with patch("newsmon.app.poll_sources", new=poll), \
         patch("newsmon.app.webbrowser.open", new=opened):
        app = NewsmonApp(Config(topic="t", interval=3600))
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
    opened.assert_called_once_with("https://example.com/quake")
