import json
import re
from dataclasses import dataclass

from app.domain.invariant import Invariant
from app.domain.models import ChatMessage, LLMGatewayError

GUARD_SYSTEM = (
    "Ты — страж инвариантов проекта. Тебе дают список инвариантов и сообщение "
    "пользователя. Реши, просит ли пользователь решение, которое нарушает хотя "
    "бы один инвариант. Сомнительные случаи считай НЕ нарушением. "
    "Ответь СТРОГО одним JSON-объектом и ничем больше: "
    '{"violates": true|false, "invariant_id": "<id или null>", '
    '"reason": "<кратко, по-русски>"}.'
)

_FENCED = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class Violation:
    invariant_id: str
    reason: str


@dataclass(frozen=True)
class GuardOutcome:
    violation: Violation | None
    tokens: int = 0


def build_invariants_block(invariants: list[Invariant]) -> str:
    lines = ["## Инварианты проекта (нарушать нельзя)"]
    for item in invariants:
        lines.append(f"- [{item.category_label}] {item.text}")
    lines.append(
        "Работай строго в этих рамках. Если запрос им противоречит — откажись "
        "и кратко объясни почему."
    )
    return "\n".join(lines)


def build_guard_messages(
    message: str, invariants: list[Invariant]
) -> list[ChatMessage]:
    listing = "\n".join(f"{item.id}: {item.text}" for item in invariants)
    return [
        ChatMessage(role="system", content=GUARD_SYSTEM),
        ChatMessage(role="system", content=f"Инварианты:\n{listing}"),
        ChatMessage(role="user", content=message),
    ]


async def check_request(
    message: str, invariants: list[Invariant], gateway
) -> GuardOutcome:
    if not invariants:
        return GuardOutcome(None)
    try:
        response = await gateway.complete(
            build_guard_messages(message, invariants)
        )
    except LLMGatewayError:
        return GuardOutcome(None)
    violation = _parse_violation(response.text)
    return GuardOutcome(violation, response.usage.total_tokens)


def build_refusal(violation: Violation, invariant: Invariant | None) -> str:
    if invariant is not None:
        head = (
            "Не могу предложить это решение: оно нарушает инвариант "
            f"«{invariant.text}» ({invariant.category_label})."
        )
    else:
        head = (
            "Не могу предложить это решение: оно нарушает установленный "
            "инвариант."
        )
    parts = [head]
    if violation.reason:
        parts.append(f"Причина: {violation.reason}")
    parts.append("Могу предложить вариант, который не нарушает инварианты.")
    return "\n\n".join(parts)


def _parse_violation(text: str) -> Violation | None:
    payload = _first_json_object(text)
    if payload is None or not _is_true(payload.get("violates")):
        return None
    return Violation(
        invariant_id=str(payload.get("invariant_id") or ""),
        reason=str(payload.get("reason") or "").strip(),
    )


def _is_true(value) -> bool:
    if value is True:
        return True
    return isinstance(value, str) and value.strip().lower() == "true"


def _first_json_object(text: str) -> dict | None:
    for candidate in _candidates(text):
        try:
            payload = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _candidates(text: str):
    for block in _FENCED.findall(text):
        yield block.strip()
    yield text.strip()
