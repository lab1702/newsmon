from __future__ import annotations

from datetime import datetime, tzinfo
from urllib.parse import urlsplit

from newsmon.health import Health, SourceResult
from newsmon.models import NewsItem


def is_browsable_url(url: str) -> bool:
    """True only for http/https URLs with a host — safe to hand to the OS browser."""
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and bool(parts.netloc)


_HEALTH_ICONS = {Health.OK: "✅", Health.SLOW: "⚠️", Health.FAILED: "❌"}


def format_row(item: NewsItem, tz: tzinfo) -> tuple[str, str, str]:
    when = item.published.astimezone(tz).strftime("%H:%M")
    return item.source, when, item.title


def render_sidebar(
    results: list[SourceResult],
    new_count: int,
    enabled: set[str] | None = None,
) -> str:
    """Render the sidebar. Each source is prefixed with its 1-based toggle key;
    sources not in `enabled` are dimmed and marked "off" (None means all on)."""
    lines = [f"🔴 {new_count} new", ""]
    for idx, result in enumerate(results, 1):
        health = _HEALTH_ICONS.get(result.health, "?")
        line = f"{idx} {health} {result.name:<7} {result.count}"
        if enabled is not None and result.name not in enabled:
            line = f"[dim]{line}  off[/dim]"
        lines.append(line)
    return "\n".join(lines)
