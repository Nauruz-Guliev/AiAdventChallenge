import asyncio

import pytest

from app.application.concurrency import OverloadedGuard
from app.domain.models import Overloaded


async def test_slot_allows_up_to_limit():
    guard = OverloadedGuard(max_concurrency=2, max_queue=0)
    async with guard.slot():
        async with guard.slot():
            assert guard.active == 2
    assert guard.active == 0


async def test_slot_queues_then_overloads():
    guard = OverloadedGuard(max_concurrency=1, max_queue=1)
    await guard.acquire()
    waiter = asyncio.create_task(guard.acquire())
    await asyncio.sleep(0)
    with pytest.raises(Overloaded):
        await guard.acquire()
    await guard.release()
    await waiter
    assert guard.active == 1
    await guard.release()


async def test_release_notifies_next():
    guard = OverloadedGuard(max_concurrency=1, max_queue=1)
    order: list[str] = []

    async def worker(name: str):
        async with guard.slot():
            order.append(name)

    first = asyncio.create_task(worker("a"))
    await asyncio.sleep(0)
    second = asyncio.create_task(worker("b"))
    await asyncio.sleep(0)
    await asyncio.gather(first, second)
    assert order == ["a", "b"]
