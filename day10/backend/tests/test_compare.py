import pytest

from app.application.agent import Agent
from app.application.compare import (
    CONTROL_FACTS,
    FINAL_QUESTION,
    SCENARIO_TURNS,
    ContextComparator,
    check_survival,
)
from app.domain.models import LLMResponse, TokenUsage, UsageConfig
from app.infrastructure.json_chat_repository import JsonChatRepository
from app.infrastructure.token_counter import TiktokenCounter


def test_scenario_contains_every_control_fact():
    joined = "\n".join(SCENARIO_TURNS) + "\n" + FINAL_QUESTION
    for label, needle in CONTROL_FACTS.items():
        assert needle in joined, label


def test_check_survival_detects_missing():
    answer = "ТЗ: код Буревестник, бюджет 1200"
    survived = check_survival(answer)
    assert survived["кодовое имя"] and survived["бюджет"]
    assert not survived["срок"]


class CompareGateway:
    """Возвращает все контрольные факты в финале; фейковые токены = реальный размер запроса."""

    def __init__(self, counter, fail_mode=None):
        self.counter = counter
        self.fail_mode = fail_mode
        self.fact_update_seen = False

    async def complete(self, messages):
        prompt = self.counter.count_messages(messages)
        is_facts_update = messages[0].role == "system" and "facts" in messages[0].content.lower()
        if is_facts_update:
            if self.fail_mode == "facts":
                raise RuntimeError("экстрактор упал")
            import json

            text = json.dumps(
                {label: value for label, value in CONTROL_FACTS.items()},
                ensure_ascii=False,
            )
        elif messages[-1].content == FINAL_QUESTION:
            text = "ТЗ готово. " + "; ".join(
                f"{label}: {value}" for label, value in CONTROL_FACTS.items()
            )
        else:
            text = "ок"
        completion = self.counter.count_messages(
            [messages[0].__class__(role="assistant", content=text)]
        )
        return LLMResponse(
            text=text,
            model="fake",
            usage=TokenUsage(prompt, completion, prompt + completion),
        )


def build_comparator(tmp_path, fail_mode=None):
    repository = JsonChatRepository(tmp_path / "chats.json")
    counter = TiktokenCounter()
    gateway = CompareGateway(counter, fail_mode=fail_mode)

    class ModeAwareAgent(Agent):
        async def run(self, chat_id, user_text, mode="sliding"):
            if mode == "facts" and fail_mode == "facts":
                raise RuntimeError("экстрактор упал")
            return await super().run(chat_id, user_text, mode=mode)

    agent = ModeAwareAgent(gateway, repository, counter, UsageConfig())
    return ContextComparator(agent, repository), repository


@pytest.mark.asyncio
async def test_comparator_runs_all_modes_and_scores(tmp_path):
    comparator, repository = build_comparator(tmp_path)

    results = await comparator.run()

    assert [r.mode for r in results] == ["full", "sliding", "facts", "branching"]
    assert len(await repository.list_chats()) == 4
    for result in results:
        assert result.error is None
        assert result.calls >= 11
        assert sum(result.survived.values()) == 6
    full = next(r for r in results if r.mode == "full")
    sliding = next(r for r in results if r.mode == "sliding")
    assert sliding.prompt_tokens < full.prompt_tokens
    facts = next(r for r in results if r.mode == "facts")
    assert facts.fact_update_tokens > 0


@pytest.mark.asyncio
async def test_comparator_isolates_mode_failure(tmp_path):
    comparator, _ = build_comparator(tmp_path, fail_mode="facts")

    results = await comparator.run(modes=("facts", "full"))

    facts = next(r for r in results if r.mode == "facts")
    full = next(r for r in results if r.mode == "full")
    assert facts.error is not None and facts.chat_id
    assert full.error is None
    assert sum(full.survived.values()) == 6
