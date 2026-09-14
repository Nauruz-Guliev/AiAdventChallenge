from dataclasses import dataclass, field
from time import perf_counter

from app.application.agent import Agent
from app.application.context_strategy import CONTEXT_MODES
from app.application.ports.chat_repository import ChatRepository

CONTROL_FACTS = {
    "кодовое имя": "Буревестник",
    "бюджет": "1200",
    "срок": "15 декабря",
    "инфраструктура": "без внешнего облака",
    "хранилище": "PostgreSQL",
    "ритуал": "отчёт по пятницам",
}

SCENARIO_TURNS = [
    "Работаем над ТЗ внутреннего сервиса. Кодовое имя продукта — Буревестник.",
    "Целевая аудитория — служба поддержки, 15 человек.",
    "Бюджет проекта — 1200 человеко-дней, больше нельзя.",
    "Жесткое ограничение: только on-prem, без внешнего облака.",
    "Хранилище — PostgreSQL, ничего экзотического.",
    "Срок сдачи — до 15 декабря.",
    "Регулярный ритуал: отчёт по пятницам.",
    "Интеграция только с внутренним helpdesk.",
    "Интерфейс: тёмная тема и управление с клавиатуры.",
    "Отчётность: экспорт в CSV и дашборд метрик.",
]

FINAL_QUESTION = (
    "Собери ТЗ кратко списком. Какое кодовое имя продукта и бюджет "
    "в человеко-днях?"
)


def check_survival(answer: str) -> dict[str, bool]:
    return {
        label: needle in answer for label, needle in CONTROL_FACTS.items()
    }


@dataclass
class CompareModeResult:
    mode: str
    chat_id: str
    survived: dict[str, bool] = field(default_factory=dict)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    fact_update_tokens: int = 0
    calls: int = 0
    duration_ms: int = 0
    error: str | None = None


class ContextComparator:
    def __init__(self, agent: Agent, repository: ChatRepository):
        self._agent = agent
        self._repository = repository

    async def run(self, modes: tuple[str, ...] = CONTEXT_MODES) -> list[CompareModeResult]:
        import asyncio

        return list(
            await asyncio.gather(*(self._run_mode(mode) for mode in modes))
        )

    async def _run_mode(self, mode: str) -> CompareModeResult:
        chat = await self._repository.create_chat(title=f"⚖ {mode}")
        result = CompareModeResult(mode=mode, chat_id=chat.id)
        started_at = perf_counter()

        async def exchange(text: str) -> None:
            answer = await self._agent.run(chat.id, text, mode=mode)
            usage = answer.usage
            result.prompt_tokens += usage.prompt_tokens_api
            result.completion_tokens += usage.completion_tokens_api
            if usage.context is not None:
                result.fact_update_tokens += usage.context.fact_update_tokens
            result.calls += 1

        try:
            for index, turn in enumerate(SCENARIO_TURNS, start=1):
                await exchange(turn)
                if mode == "branching" and index == 5:
                    fresh = await self._repository.get_chat(chat.id)
                    await self._repository.fork_branch(
                        chat.id, len(fresh.messages), "ветка Б"
                    )
            final = await self._agent.run(chat.id, FINAL_QUESTION, mode=mode)
            usage = final.usage
            result.prompt_tokens += usage.prompt_tokens_api
            result.completion_tokens += usage.completion_tokens_api
            if usage.context is not None:
                result.fact_update_tokens += usage.context.fact_update_tokens
            result.calls += 1
            result.survived = check_survival(final.answer)
        except Exception as error:
            result.error = str(error)[:300]
            result.survived = check_survival("")
        result.duration_ms = round((perf_counter() - started_at) * 1000)
        return result
