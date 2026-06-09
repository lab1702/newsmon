import pytest

from newsmon.sources import ALL_SOURCE_NAMES, build_sources


def test_all_source_names():
    assert ALL_SOURCE_NAMES == ["web", "hn", "reddit", "youtube", "twitch", "x"]


def test_build_all_by_default():
    sources = build_sources(None)
    assert [s.name for s in sources] == ALL_SOURCE_NAMES


def test_build_subset_preserves_canonical_order():
    sources = build_sources(["x", "web"])
    assert [s.name for s in sources] == ["web", "x"]


def test_build_unknown_source_raises():
    with pytest.raises(ValueError, match="unknown source"):
        build_sources(["pigeon"])
