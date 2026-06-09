from __future__ import annotations

from datetime import datetime, tzinfo

from newsmon.health import Health, SourceResult
from newsmon.models import NewsItem

SOURCE_ICONS = {
    "web": "📰",
    "hn": "🟧",
    "reddit": "👽",
    "youtube": "▶️",
    "twitch": "🟣",
    "x": "𝕏",
}
_HEALTH_ICONS = {Health.OK: "✅", Health.SLOW: "⚠️", Health.FAILED: "❌"}


def format_row(item: NewsItem, tz: tzinfo) -> tuple[str, str, str]:
    icon = SOURCE_ICONS.get(item.source, "•")
    when = item.published.astimezone(tz).strftime("%H:%M")
    return icon, when, item.title


def render_sidebar(results: list[SourceResult], new_count: int) -> str:
    lines = [f"🔴 {new_count} new", ""]
    for result in results:
        health = _HEALTH_ICONS.get(result.health, "?")
        lines.append(f"{health} {result.name:<7} {result.count}")
    return "\n".join(lines)
