from __future__ import annotations

from datetime import datetime, tzinfo
from urllib.parse import urlsplit

from newsmon.health import Health, SourceResult
from newsmon.models import NewsItem
from newsmon.sources.base import clean_text

# Digit keys 1-9 toggle the Nth source; sources past the 9th have no toggle key.
MAX_TOGGLE_KEYS = 9

# Display cap for a rendered title; bounds a pathological multi-megabyte title
# from a hostile feed (the per-parser caps are inconsistent or absent).
_TITLE_MAX = 500


def is_browsable_url(url: str) -> bool:
    """True only for http/https URLs with a host — safe to hand to the OS browser.
    Any control character (tab/CR/LF, etc.) is rejected: ``urlsplit`` silently
    strips them, so such a URL would pass this check yet keep the control char in
    the raw string we open/copy — an embedded newline in a copied URL is a
    terminal paste-injection vector."""
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in url):
        return False
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and bool(parts.netloc)


_HEALTH_ICONS = {Health.OK: "✅", Health.SLOW: "⚠️", Health.FAILED: "❌"}


def format_row(
    item: NewsItem, tz: tzinfo, now: datetime | None = None
) -> tuple[str, str, str]:
    try:
        local = item.published.astimezone(tz)
    except (OverflowError, OSError, ValueError):
        # A boundary-year timestamp (year 1 or 9999) that slipped past a parser
        # overflows the local-zone conversion. format_row runs in the shared
        # render loop outside safe_fetch, so fall back to the raw UTC value
        # rather than let one hostile item crash the whole TUI.
        local = item.published
    # Show only HH:MM for today's items; once the recency window (--hours) can
    # span more than a day, prefix the date so same-time items on different days
    # don't render identically.
    today = (now or datetime.now(tz)).date()
    fmt = "%H:%M" if local.date() == today else "%m-%d %H:%M"
    # Single sanitization choke point for the untrusted title before it reaches
    # the terminal via Text(): strip ANSI/control escapes and bidi overrides so
    # no individual parser can forget to (most don't sanitize their titles).
    return item.source, local.strftime(fmt), clean_text(item.title, max_len=_TITLE_MAX)


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
        # Only the first MAX_TOGGLE_KEYS sources get a digit toggle key; show a
        # blank rather than an unpressable number for any beyond that.
        prefix = str(idx) if idx <= MAX_TOGGLE_KEYS else " "
        line = f"{prefix} {health} {result.name:<7} {result.count}"
        if enabled is not None and result.name not in enabled:
            line = f"[dim]{line}  off[/dim]"
        lines.append(line)
    return "\n".join(lines)
