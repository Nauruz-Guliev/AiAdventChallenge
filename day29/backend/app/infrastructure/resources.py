from __future__ import annotations

import asyncio

import psutil

from app.domain.models import ResourceSample


def find_ollama_processes() -> list:
    procs = []
    for p in psutil.process_iter(["name"]):
        try:
            name = (p.info.get("name") or "").lower()
        except Exception:  # noqa: BLE001
            continue
        if name.startswith("ollama"):
            procs.append(p)
    return procs


class ResourceSampler:
    def __init__(self, interval: float = 0.5, processes=None) -> None:
        self._interval = interval
        self._procs = list(processes) if processes is not None else find_ollama_processes()
        self._rss_peak = 0.0
        self._cpu: list[float] = []
        self._task = None
        self._running = False

    async def start(self) -> None:
        if not self._procs:
            return
        for p in self._procs:
            try:
                p.cpu_percent(None)
            except Exception:  # noqa: BLE001
                pass
        self._running = True
        self._sample()
        self._task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        while self._running:
            self._sample()
            await asyncio.sleep(self._interval)

    def _sample(self) -> None:
        for p in self._procs:
            try:
                self._rss_peak = max(self._rss_peak, float(p.memory_info().rss))
            except Exception:  # noqa: BLE001
                pass
            try:
                self._cpu.append(float(p.cpu_percent(None)))
            except Exception:  # noqa: BLE001
                pass

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def result(self) -> ResourceSample:
        cpu = sum(self._cpu) / len(self._cpu) if self._cpu else 0.0
        return ResourceSample(
            rss_peak_mb=round(self._rss_peak / 1e6, 1), cpu_percent=round(cpu, 1)
        )


async def model_size_gb(client, model: str) -> float:
    models = await client.tags()
    base = model.split(":")[0]
    for m in models:
        if m.get("name") == model:
            return round(float(m.get("size", 0)) / 1e9, 2)
    for m in models:
        if str(m.get("name", "")).startswith(base):
            return round(float(m.get("size", 0)) / 1e9, 2)
    return 0.0


async def size_vram_gb(client, model: str) -> float:
    for m in await client.ps():
        if m.get("name") == model:
            return round(float(m.get("size_vram", 0)) / 1e9, 2)
    return 0.0
