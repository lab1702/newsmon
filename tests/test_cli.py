import pytest

from newsmon.cli import Config, parse_args


def test_defaults():
    cfg = parse_args(["earthquake"])
    assert cfg == Config(
        topic="earthquake", hours=6, interval=60, bell=False, sources=None
    )


def test_all_flags():
    cfg = parse_args(
        ["big quake", "--hours", "3", "--interval", "30", "--bell",
         "--sources", "web,hn"]
    )
    assert cfg.topic == "big quake"
    assert cfg.hours == 3
    assert cfg.interval == 30
    assert cfg.bell is True
    assert cfg.sources == ["web", "hn"]


def test_unknown_source_rejected():
    with pytest.raises(SystemExit):
        parse_args(["quake", "--sources", "web,pigeon"])
