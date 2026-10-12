import pytest

from app.presentation.streamer import TelegramMessageStreamer


class FakeTG:
    def __init__(self):
        self.sent: list[str] = []
        self.edits: list[str] = []

    async def send(self, text: str):
        self.sent.append(text)
        return f"msg{len(self.sent)}"

    async def edit(self, message, text: str, parse_mode=None):
        self.edits.append(text)


@pytest.fixture
def tg():
    return FakeTG()


async def test_start_sends_placeholder(tg):
    s = TelegramMessageStreamer(tg.send, tg.edit, min_interval=0)
    await s.start()
    assert tg.sent == ["💭 думает…"]


async def test_throttle_skips_edits(tg):
    s = TelegramMessageStreamer(tg.send, tg.edit, min_interval=999)
    await s.start()
    await s.push("a")
    await s.push("b")
    assert tg.edits == []


async def test_force_flushes(tg):
    s = TelegramMessageStreamer(tg.send, tg.edit, min_interval=999)
    await s.start()
    await s.push("hello", force=True)
    assert "hello" in tg.edits


async def test_finish_adds_footer(tg):
    s = TelegramMessageStreamer(tg.send, tg.edit, min_interval=0)
    await s.start()
    await s.push("привет", force=True)
    await s.finish("привет", "🤖 m · локально")
    assert any("локально" in e for e in tg.edits)


async def test_overflow_starts_new_message(tg):
    s = TelegramMessageStreamer(tg.send, tg.edit, min_interval=0, limit=20)
    await s.start()
    await s.push("x" * 50, force=True)
    assert s.overflowed is True
    assert len(tg.sent) >= 2


async def test_no_duplicate_edit(tg):
    s = TelegramMessageStreamer(tg.send, tg.edit, min_interval=0)
    await s.start()
    await s.push("same", force=True)
    before = len(tg.edits)
    await s.push("", force=True)
    assert len(tg.edits) == before
