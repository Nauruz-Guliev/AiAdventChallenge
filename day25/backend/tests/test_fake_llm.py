import json

from app.infrastructure.fake_llm import FakeLLM


async def test_fake_llm_returns_configured_answer():
    llm = FakeLLM(answer="hello")
    assert await llm.complete([{"role": "user", "content": "q"}]) == "hello"


async def test_fake_llm_returns_judge_score_for_judge_prompt():
    llm = FakeLLM(judge_score=0.5)
    reply = await llm.complete([
        {"role": "system", "content": "JUDGE ..."},
        {"role": "user", "content": "x"},
    ])
    assert json.loads(reply)["score"] == 0.5
