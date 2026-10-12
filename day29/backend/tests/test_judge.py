import pytest

from app.application.judge_deepseek import DeepSeekJudge, parse_score
from app.ports.llm import Completion


def test_parse_score_variants():
    assert parse_score('{"score": 0.7, "reason": "ok"}') == 0.7
    assert parse_score("I'd say 0.5") == 0.5
    assert parse_score("nonsense") == 0.0
    assert parse_score('{"score": 2}') == 1.0


class FakeLLM:
    def __init__(self, text):
        self._text = text

    async def complete(self, messages, think=False):
        return Completion(text=self._text)


@pytest.mark.asyncio
async def test_judge_scores():
    j = DeepSeekJudge(FakeLLM('{"score": 0.8, "reason": "good"}'))
    assert await j.score("q", "exp", "answer") == 0.8
