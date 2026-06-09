from __future__ import annotations

import webbrowser
from datetime import datetime, timedelta, timezone

import httpx
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import DataTable, Footer, Header, Static

from newsmon.aggregator import SeenTracker, merge_items, poll_sources
from newsmon.cli import Config
from newsmon.models import NewsItem
from newsmon.sources import build_sources
from newsmon.ui import format_row, is_browsable_url, render_sidebar

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
    ] + [
        # Digit keys toggle the Nth active source (see sidebar); hidden from footer.
        Binding(str(n), f"toggle_source({n})", f"Toggle source {n}", show=False)
        for n in range(1, 10)
    ]

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self.sources = build_sources(config.sources)
        self.tracker = SeenTracker()
        self.new_count = 0
        self._new_keys: set[str] = set()
        self.enabled: set[str] = {s.name for s in self.sources}
        self.items: list[NewsItem] = []
        self._all_items: list[NewsItem] = []
        self._latest_results: list = []
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
        self._new_keys = {item.dedup_key for item in new}
        self._all_items = merged
        self._latest_results = results
        self._refresh_view()
        if new and self.config.bell:
            self.bell()

    def _refresh_view(self) -> None:
        """Apply the source filter to the last poll and re-render (no network)."""
        self.items = [i for i in self._all_items if i.source in self.enabled]
        self._render(self._latest_results)

    def action_toggle_source(self, n: int) -> None:
        if not 1 <= n <= len(self.sources):
            return
        name = self.sources[n - 1].name
        if name in self.enabled:
            self.enabled.discard(name)
        else:
            self.enabled.add(name)
        self._refresh_view()

    def _render(self, results) -> None:
        table = self.query_one("#stream", DataTable)
        table.clear()
        tz = datetime.now().astimezone().tzinfo
        for item in self.items:
            icon, when, title = format_row(item, tz=tz)
            cell = Text(title, style="bold yellow") if item.dedup_key in self._new_keys else title
            table.add_row(icon, when, cell)
        self.query_one("#sidebar", Static).update(
            render_sidebar(results, self.new_count, self.enabled)
        )

    def _selected_item(self):
        table = self.query_one("#stream", DataTable)
        row = table.cursor_row
        if row >= len(self.items):
            return None
        return self.items[row]

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # The focused DataTable consumes Enter (and click) as a row selection,
        # shadowing the App-level "enter" binding — so open from this message.
        self.action_open()

    def action_open(self) -> None:
        item = self._selected_item()
        if item is None:
            return
        if is_browsable_url(item.url):
            webbrowser.open(item.url)
        else:
            self.notify(f"Refused to open unsafe URL: {item.url}", severity="warning")

    def action_copy(self) -> None:
        item = self._selected_item()
        if item is not None:
            self.copy_to_clipboard(item.url)
            self.notify(f"Copied: {item.url}")


def run_app(config: Config) -> None:
    NewsmonApp(config).run()
