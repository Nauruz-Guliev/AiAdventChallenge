import pytest

from app.infrastructure.resources import ResourceSampler, model_size_gb, size_vram_gb


class FakeProc:
    def __init__(self, rss):
        self._rss = rss

    def memory_info(self):
        return type("M", (), {"rss": self._rss})()

    def cpu_percent(self, interval=None):
        return 42.0


@pytest.mark.asyncio
async def test_sampler_collects_peak_rss_and_cpu():
    s = ResourceSampler(interval=0.01, processes=[FakeProc(5_000_000)])
    await s.start()
    await s.stop()
    out = s.result()
    assert out.rss_peak_mb == 5.0 and out.cpu_percent == 42.0


@pytest.mark.asyncio
async def test_sampler_without_process_returns_zeros():
    s = ResourceSampler(interval=0.01, processes=[])
    await s.start()
    await s.stop()
    assert s.result().rss_peak_mb == 0.0


class FakeClient:
    async def tags(self):
        return [{"name": "gemma4:12b", "size": 8_000_000_000}]

    async def ps(self):
        return [{"name": "gemma4:12b", "size_vram": 5_000_000_000}]


@pytest.mark.asyncio
async def test_model_size_and_vram():
    c = FakeClient()
    assert await model_size_gb(c, "gemma4:12b") == 8.0
    assert await size_vram_gb(c, "gemma4:12b") == 5.0
