from newsmon.health import Health, SourceResult


def test_source_result_defaults():
    r = SourceResult(name="web", items=[], health=Health.OK)
    assert r.error is None
    assert r.elapsed == 0.0
    assert r.count == 0


def test_count_reflects_items():
    r = SourceResult(name="web", items=[object(), object()], health=Health.OK)
    assert r.count == 2
