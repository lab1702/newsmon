from __future__ import annotations

import argparse
from dataclasses import dataclass

from newsmon.sources import ALL_SOURCE_NAMES


@dataclass
class Config:
    topic: str
    hours: int = 6
    interval: int = 60
    bell: bool = False
    sources: list[str] | None = None


def _positive_int(value: str) -> int:
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {value}")
    return ivalue


def _sources(value: str) -> list[str]:
    names = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [n for n in names if n not in ALL_SOURCE_NAMES]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown source(s): {', '.join(unknown)}")
    return names


def parse_args(argv: list[str] | None = None) -> Config:
    parser = argparse.ArgumentParser(
        prog="newsmon", description="Keyless breaking-news TUI"
    )
    parser.add_argument("topic", help="topic keywords (quote if multi-word)")
    parser.add_argument("--hours", type=_positive_int, default=6, help="recency window")
    parser.add_argument(
        "--interval", type=_positive_int, default=60, help="poll seconds"
    )
    parser.add_argument("--bell", action="store_true", help="bell on live arrivals")
    parser.add_argument(
        "--sources",
        type=_sources,
        default=None,
        help=f"comma list from: {','.join(ALL_SOURCE_NAMES)}",
    )
    ns = parser.parse_args(argv)
    return Config(ns.topic, ns.hours, ns.interval, ns.bell, ns.sources)


def main(argv: list[str] | None = None) -> None:
    config = parse_args(argv)
    from newsmon.app import run_app

    run_app(config)
