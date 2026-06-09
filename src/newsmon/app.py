from __future__ import annotations

import webbrowser
from datetime import datetime, timedelta, timezone

import httpx
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import DataTable, Footer, Header, Static

from newsmon.aggregator import SeenTracker, merge_items, poll_sources
from newsmon.cli import Config
from newsmon.models import NewsItem
from newsmon.sources import build_sources
from newsmon.ui import format_row, render_sidebar

REQUEST_TIMEOUT = 15.0
SLOW_AFTER = 8.0


class NewsmonApp(App):
    CSS = """
    #sidebar { width: 24; border-right: solid $accent; padding: 0 1; }
    #stream { width: 1fr; }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("enter", "open", "Open"),
        ("y", "copy", "Copy URL"),
    ]

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self.sources = build_sources(config.sources)
        self.tracker = SeenTracker()
        self.new_count = 0
        self.items: list[NewsItem] = []
        self._client: httpx.AsyncClient | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            yield Static(id="sidebar")
            table = DataTable(id="stream", cursor_type="row")
            table.add_columns(" ", "time", "title")
            yield table
        yield Footer()

    async def on_mount(self) -> None:
        self.title = f"newsmon — {self.config.topic}"
        self._client = httpx.AsyncClient(
            follow_redirects=True, headers={"User-Agent": "newsmon/0.1"}
        )
        await self.action_refresh()
        self.set_interval(self.config.interval, self.action_refresh)

    async def on_unmount(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def action_refresh(self) -> None:
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=self.config.hours)
        results = await poll_sources(
            self.sources, self._client, self.config.topic, since,
            timeout=REQUEST_TIMEOUT, slow_after=SLOW_AFTER,
        )
        merged = merge_items(results, since)
        new = self.tracker.mark_new(merged)
        self.new_count += len(new)
        self.items = merged
        self._render(results)
        if new and self.config.bell:
            self.bell()

    def _render(self, results) -> None:
        table = self.query_one("#stream", DataTable)
        table.clear()
        tz = datetime.now().astimezone().tzinfo
        for item in self.items:
            icon, when, title = format_row(item, tz=tz)
            table.add_row(icon, when, title)
        self.query_one("#sidebar", Static).update(
            render_sidebar(results, self.new_count)
        )

    def _selected_item(self):
        table = self.query_one("#stream", DataTable)
        row = table.cursor_row
        if row >= len(self.items):
            return None
        return self.items[row]

    def action_open(self) -> None:
        item = self._selected_item()
        if item is not None:
            webbrowser.open(item.url)

    def action_copy(self) -> None:
        item = self._selected_item()
        if item is not None:
            self.copy_to_clipboard(item.url)
            self.notify(f"Copied: {item.url}")


def run_app(config: Config) -> None:
    NewsmonApp(config).run()
