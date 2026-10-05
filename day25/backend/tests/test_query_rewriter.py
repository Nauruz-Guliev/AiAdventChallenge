import asyncio

from app.application.query_rewriter import QueryRewriter


class _FakeLLM:
    def __init__(self, reply):
        self.reply = reply

    async def complete(self, messages):
        return self.reply


def test_rewrite_returns_llm_query():
    rw = QueryRewriter(_FakeLLM("ktor client multiplatform setup"))
    assert asyncio.run(rw.rewrite("Как настроить Ktor?")) == "ktor client multiplatform setup"


def test_rewrite_fallback_on_blank():
    rw = QueryRewriter(_FakeLLM("   "))
    assert asyncio.run(rw.rewrite("Как настроить Ktor?")) == "Как настроить Ktor?"


def test_rewrite_disabled_passthrough():
    rw = QueryRewriter(_FakeLLM("x"), enabled=False)
    assert asyncio.run(rw.rewrite("вопрос")) == "вопрос"
