# newsmon — Keyless Breaking-News TUI

**Date:** 2026-06-09
**Status:** Approved design

## Summary

`newsmon` is a terminal UI application that monitors the public web, YouTube,
Twitch, X/Twitter, and other useful sources for **breaking news** matching a
topic supplied on the command line. It uses only publicly available resources
that require **no API keys or registration**. Sources that cannot be reached
cleanly without keys are included on a best-effort basis and clearly marked as
unreliable.

Built in **Python with the Textual TUI framework**.

## Goals

- Monitor a user-specified topic across multiple public sources, keyless.
- Surface genuinely *breaking* (recent + live-arriving) items prominently.
- Degrade gracefully: flaky/dead sources never crash the app and their state
  is visible to the user.
- Stay simple and focused (YAGNI).

## Non-Goals

- No API-key-based integrations (deferred; not in scope).
- No persistence/history database, no historical search UI.
- No in-TUI article reader (selection opens the system browser instead).

## CLI

```
newsmon "topic keywords" [--hours 6] [--interval 60] [--bell] \
        [--sources web,reddit,hn,youtube,twitch,x]
```

| Arg / Flag | Default | Meaning |
|---|---|---|
| `topic` (positional, required) | — | Search keywords, quoted if multi-word |
| `--hours` | 6 | Recency window; items older than this are dropped |
| `--interval` | 60 | Poll cadence in seconds |
| `--bell` | off | Emit terminal bell when a new item arrives live |
| `--sources` | all | Comma list to enable a subset of sources |

## Sources

Keyless-first. Reliable sources carry the experience; fragile scrapers are
best-effort and surfaced with a health indicator.

| Source | Method | Reliability |
|---|---|---|
| Web news | Google News RSS search (`news.google.com/rss/search?q=`) | solid |
| Hacker News | Algolia search API (`hn.algolia.com/api/v1/search_by_date`) | solid |
| Reddit | `reddit.com/search.json?sort=new` with a custom User-Agent | usually fine |
| YouTube | Scrape search results page sorted by upload date; parse `ytInitialData` | fragile |
| Twitch | Public web Client-ID GQL search for live streams/videos | fragile |
| X/Twitter | Nitter instance search RSS, rotating through an instance list | very fragile |

Hacker News and Reddit are included as the "other useful sources" — both are
genuinely keyless and dependable, balancing the flaky Twitch/X paths.

## Architecture

### Async core
- `asyncio` + `httpx` for concurrent fetching.
- Each source is an isolated module implementing one interface:
  - `name: str`
  - `async fetch(topic: str, since: datetime) -> list[NewsItem]`
  - reports a health status (ok / slow / failed) per poll.
- Per-source `try/except` + timeout. One slow or failing source cannot block
  or crash the others.

### Data model
`NewsItem` dataclass:
- `source: str` — source identifier
- `title: str`
- `url: str`
- `published: datetime` — timezone-aware
- `summary: str`
- `extra: dict` — source-specific metadata (e.g. author, channel, viewers)

### Aggregator
On each `--interval` tick:
1. Poll all enabled sources concurrently.
2. Dedup by normalized URL.
3. Filter to the `--hours` recency window.
4. Merge newest-first.
5. Diff against a seen-ID set to detect **live arrivals** (items appearing
   after launch), which drive the highlight/flash, the "new" counter, and the
   optional bell.

## TUI (Textual)

- **Main stream**: merged list, newest-first. Each row = source icon + local
  time + title. Live-arriving items are highlighted/flashed and increment a
  "🔴 N new" counter.
- **Sidebar**: per-source health (✅ ok / ⚠️ slow / ❌ failed) and item counts,
  making fragile sources' state visible.
- **Filtering**: number keys / clicks toggle sources on/off in the stream view.
- **Selection**: `Enter` opens the item URL in the default browser
  (`webbrowser` / `xdg-open`); `y` copies the URL to the clipboard.
- **Footer**: keybinding hints; `r` manual refresh, `q` quit.

## Error Handling

- Network and parse failures degrade to the source's health status and are
  shown in the sidebar; they never propagate to crash the UI.
- Fragile scrapers (YouTube/Twitch/X) are expected to fail intermittently; this
  is normal and visible, not fatal.

## Testing

- Each source parser is unit-tested against saved sample responses (fixtures),
  so scraper breakage is detectable without live network calls.
- Aggregator logic — dedup, recency window, live-arrival detection — is tested
  in isolation with synthetic `NewsItem` sets.

## Open Questions / Future Work

- Optional API-key integrations to make Twitch/X reliable (explicitly deferred).
- Configurable extra RSS feeds.
- Desktop notifications beyond the terminal bell.
