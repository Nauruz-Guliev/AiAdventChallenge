from app.application.invariant_guard import (
    Violation,
    build_refusal,
    check_request,
)
from app.domain.invariant import Invariant
from app.domain.models import LLMGatewayError, LLMResponse, TokenUsage


class Gateway:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    async def complete(self, messages):
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResponse(item, "m", TokenUsage(10, 2, 12))


INVARIANTS = [
    Invariant(id="i1", text="Только Python", category="stack"),
    Invariant(id="i2", text="Без новых зависимостей", category="stack"),
]


async def test_no_invariants_skips_the_model_call():
    gateway = Gateway()

    outcome = await check_request("что угодно", [], gateway)

    assert outcome.violation is None
    assert gateway.calls == 0


async def test_violation_is_parsed():
    gateway = Gateway(
        '{"violates": true, "invariant_id": "i1", "reason": "просит Node.js"}'
    )

    outcome = await check_request("сделай на Node.js", INVARIANTS, gateway)

    assert outcome.violation == Violation("i1", "просит Node.js")
    assert outcome.tokens == 12


async def test_fenced_json_is_parsed():
    gateway = Gateway(
        '```json\n{"violates": true, "invariant_id": "i2", "reason": "lib"}\n```'
    )

    outcome = await check_request("поставь новую библиотеку", INVARIANTS, gateway)

    assert outcome.violation is not None
    assert outcome.violation.invariant_id == "i2"


async def test_clean_request_has_no_violation():
    gateway = Gateway('{"violates": false}')

    outcome = await check_request("напиши функцию на Python", INVARIANTS, gateway)

    assert outcome.violation is None


async def test_string_false_is_not_a_violation():
    gateway = Gateway('{"violates": "false", "reason": ""}')

    outcome = await check_request("напиши функцию на Python", INVARIANTS, gateway)

    assert outcome.violation is None


async def test_unknown_invariant_id_is_still_a_violation():
    gateway = Gateway(
        '{"violates": true, "invariant_id": "zzz", "reason": "нарушение"}'
    )

    outcome = await check_request("...", INVARIANTS, gateway)

    assert outcome.violation is not None
    assert outcome.violation.invariant_id == "zzz"


async def test_malformed_answer_fails_open():
    gateway = Gateway("тут не json")

    outcome = await check_request("...", INVARIANTS, gateway)

    assert outcome.violation is None
    assert outcome.tokens == 12


async def test_gateway_error_fails_open():
    gateway = Gateway(LLMGatewayError())

    outcome = await check_request("...", INVARIANTS, gateway)

    assert outcome.violation is None


def test_refusal_names_the_invariant_and_reason():
    text = build_refusal(Violation("i1", "просит Node.js"), INVARIANTS[0])

    assert "Только Python" in text
    assert "просит Node.js" in text
    assert "инвариант" in text.lower()


def test_refusal_without_known_invariant_is_still_clear():
    text = build_refusal(Violation("zzz", "нарушение"), None)

    assert "инвариант" in text.lower()
    assert "нарушение" in text
