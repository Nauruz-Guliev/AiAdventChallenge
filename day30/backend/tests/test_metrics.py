from app.infrastructure.metrics import Metrics


def test_counters_accumulate():
    m = Metrics()
    m.inc("requests_total")
    m.inc("requests_total", 2)
    assert m.snapshot()["requests_total"] == 3


def test_percentiles_and_samples():
    m = Metrics()
    for value in range(1, 101):
        m.observe(float(value))
    assert m.percentile(50) == 50.0
    assert m.percentile(95) == 95.0
    snap = m.snapshot()
    assert snap["samples"] == 100
    assert snap["latency_ms_p50"] == 50.0


def test_empty_percentile_is_zero():
    assert Metrics().percentile(95) == 0.0


def test_snapshot_merges_extra():
    snap = Metrics().snapshot(extra={"queued_requests": 4})
    assert snap["queued_requests"] == 4
