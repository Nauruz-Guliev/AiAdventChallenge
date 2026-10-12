import pytest

from app.application.chat_service import ChatService
from app.domain.models import ChatMessage, Role
from app.infrastructure.chat_store import JsonChatStore
from app.ports.llm import StreamDelta, StreamDone


@pytest.fixture
def service(tmp_path, fake_llm, settings):
    return ChatService(JsonChatStore(tmp_path), fake_llm, settings)


async def test_first_turn_creates_state(service):
    st = service.get_state(42)
    assert st.system_prompt
    assert st.messages == []


async def test_stream_adds_history_and_persists(service, fake_llm):
    st = service.get_state(42)
    events = [e async for e in service.stream(st, ChatMessage(Role.USER, "hi"))]
    assert isinstance(events[-1], StreamDone)
    content = "".join(e.text for e in events if isinstance(e, StreamDelta))
    assert content == "Hello"
    reloaded = service.get_state(42)
    assert [m.content for m in reloaded.messages] == ["hi", "Hello"]


async def test_second_turn_includes_history(service, fake_llm):
    st = service.get_state(42)
    async for _ in service.stream(st, ChatMessage(Role.USER, "first")):
        pass
    st2 = service.get_state(42)
    async for _ in service.stream(st2, ChatMessage(Role.USER, "second")):
        pass
    payload = fake_llm.calls[-1]
    assert payload[0].role == Role.SYSTEM
    assert [m.content for m in payload] == [st2.system_prompt, "first", "Hello", "second"]


async def test_photo_placeholder_in_history(service):
    st = service.get_state(7)
    async for _ in service.stream(
        st, ChatMessage(Role.USER, "смотри", images=["BASE64"]), images=["BASE64"]
    ):
        pass
    saved = service.get_state(7)
    assert saved.messages[0].content == "[фото]"
    assert saved.messages[0].images is None


async def test_reset_keeps_system(service):
    st = service.get_state(42)
    async for _ in service.stream(st, ChatMessage(Role.USER, "hi")):
        pass
    st = service.reset(42)
    assert st.messages == []
    assert st.system_prompt


async def test_trim_limits(service, fake_llm, settings):
    st = service.get_state(42)
    for i in range(10):
        async for _ in service.stream(st, ChatMessage(Role.USER, f"m{i}")):
            pass
        st = service.get_state(42)
    assert len(st.messages) <= settings.history_max_messages


async def test_set_model_validates(service):
    st = service.get_state(42)
    assert await service.set_model(st, "gemma4:12b") is True
    assert await service.set_model(st, "nope:1b") is False


async def test_stats_contains_model_and_speed(service, fake_llm):
    st = service.get_state(42)
    async for _ in service.stream(st, ChatMessage(Role.USER, "hi")):
        pass
    text = service.stats(service.get_state(42))
    assert "gemma4:12b" in text
