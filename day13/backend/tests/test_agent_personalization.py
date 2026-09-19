from app.application.agent import Agent
from app.domain.models import (
    Chat,
    ChatMessage,
    LLMResponse,
    LongTermMemory,
    TokenUsage,
    UsageConfig,
    UserProfile,
    WorkingMemory,
)
from app.infrastructure.token_counter import TiktokenCounter


class ScriptedGateway:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, messages):
        self.calls.append(list(messages))
        return self.responses.pop(0)


class MemoryRepository:
    def __init__(self, chat):
        self.chat = chat

    async def get_chat(self, chat_id):
        return self.chat

    async def get_long_term(self):
        return LongTermMemory()

    async def append_exchange(self, chat_id, user, assistant, usage, used=None):
        self.chat.messages.extend(
            [
                ChatMessage(role="user", content=user),
                ChatMessage(
                    role="assistant", content=assistant, usage=usage, used=used
                ),
            ]
        )
        return self.chat

    async def add_candidates(self, items, source_chat_id):
        pass


class ProfileRepository:
    def __init__(self, profile):
        self.profile = profile

    async def get_active(self):
        return self.profile


def response(text="ok"):
    return LLMResponse(text, "m", TokenUsage(30, 5, 35))


def make_agent(gateway, repository, profiles):
    return Agent(
        gateway,
        repository=repository,
        counter=TiktokenCounter(),
        config=UsageConfig(),
        candidates_enabled=False,
        profiles=profiles,
    )


def chat():
    return Chat(
        id="c1",
        title="T",
        created_at="a",
        updated_at="b",
        messages=[],
        working_memory=WorkingMemory(),
    )


async def test_active_profile_is_injected_into_the_prompt():
    profiles = ProfileRepository(
        UserProfile(
            id="p1", title="Деловой", tone="formal", constraints=["без эмодзи"]
        )
    )
    gateway = ScriptedGateway([response()])
    agent = make_agent(gateway, MemoryRepository(chat()), profiles)

    result = await agent.run("c1", "привет")

    contents = [message.content for message in gateway.calls[0]]
    assert any("## Профиль пользователя" in content for content in contents)
    assert result.used["profile"]["tone"] == "formal"
    assert result.usage.memory.profile_tokens > 0


async def test_switching_profile_changes_the_prompt():
    gateway = ScriptedGateway([response(), response()])
    repository = MemoryRepository(chat())
    profiles = ProfileRepository(
        UserProfile(id="p1", title="Коротко", length="short", structure="bullets")
    )

    await make_agent(gateway, repository, profiles).run("c1", "вопрос")
    profiles.profile = UserProfile(
        id="p2", title="Наставник", length="detailed", structure="markdown"
    )
    await make_agent(gateway, repository, profiles).run("c1", "вопрос")

    first = " ".join(message.content for message in gateway.calls[0])
    second = " ".join(message.content for message in gateway.calls[1])
    assert "Объём: короткий" in first and "Объём: подробный" in second


async def test_neutral_profile_adds_no_tokens_and_no_trace():
    profiles = ProfileRepository(UserProfile(id="p1", title="Нейтральный"))
    gateway = ScriptedGateway([response()])

    result = await make_agent(
        gateway, MemoryRepository(chat()), profiles
    ).run("c1", "привет")

    contents = [message.content for message in gateway.calls[0]]
    assert not any("## Профиль пользователя" in content for content in contents)
    assert result.used["profile"] is None
    assert result.usage.memory.profile_tokens == 0
