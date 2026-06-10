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


async def test_refresh_skips_when_already_in_flight():
    """A second refresh while one is in flight is a no-op, not a stacked poll."""
    poll = AsyncMock(return_value=_one_result())
    with patch("newsmon.app.poll_sources", new=poll):
        app = NewsmonApp(Config(topic="t", interval=3600))
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            assert poll.call_count == 1  # the on_mount refresh
            app._refreshing = True
            await app.action_refresh()
            assert poll.call_count == 1  # guarded — no extra poll


async def test_selected_item_is_none_on_empty_stream():
    poll = AsyncMock(return_value=[SourceResult("web", [], Health.OK)])
    opened = MagicMock()
    with patch("newsmon.app.poll_sources", new=poll), \
         patch("newsmon.app.webbrowser.open", new=opened):
        app = NewsmonApp(Config(topic="t", interval=3600))
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            assert app._selected_item() is None
            await pilot.press("enter")
            await pilot.pause()
    opened.assert_not_called()


async def test_new_count_excludes_disabled_sources():
    """New items from a toggled-off source must not inflate the 'N new' badge."""
    now = datetime.now(timezone.utc)
    seed = SourceResult("web", [NewsItem("web", "seed", "https://e/seed", now)], Health.OK)
    poll = AsyncMock(side_effect=[
        # first poll: baseline (the seed item is marked seen, 0 new)
        [seed, SourceResult("hn", [], Health.OK)],
        # second poll: one fresh item per source
        [
            SourceResult("web", [NewsItem("web", "w", "https://e/w", now)], Health.OK),
            SourceResult("hn", [NewsItem("hn", "h", "https://e/h", now)], Health.OK),
        ],
    ])
    with patch("newsmon.app.poll_sources", new=poll):
        app = NewsmonApp(Config(topic="t", interval=3600))
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()  # on_mount → baseline poll
            assert app.new_count == 0
            app.enabled = {"web"}  # toggle hn off
            await app.action_refresh()  # second poll: web + hn both new
            assert app.new_count == 1  # only the visible (web) item counted


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
