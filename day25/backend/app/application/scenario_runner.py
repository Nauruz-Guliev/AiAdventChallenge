from __future__ import annotations

import json
import re
from pathlib import Path

from app.application.chat_service import ChatService
from app.domain.models import Message, ScenarioReport
from app.infrastructure.session_store import SessionStore


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[a-zA-Zа-яА-Я0-9]+", text or "") if len(t) >= 4}


def _goal_kept(initial: str, final: str) -> bool:
    if not final.strip():
        return False
    a, b = initial.lower(), final.lower()
    if a in b or b in a:
        return True
    return bool(_tokens(initial) & _tokens(final))


async def run_scenario(
    service: ChatService,
    store: SessionStore,
    name: str,
    goal: str,
    messages: list[dict],
) -> ScenarioReport:
    session = store.create(goal)
    initial_goal = (goal or "").strip()
    all_with_sources = True

    for m in messages:
        if m.get("role") != "user":
            continue
        text = m["text"]
        turn = await service.answer(session, text)
        if not turn.sources:
            all_with_sources = False
        session.messages.append(Message(role="user", text=text))
        session.messages.append(Message(
            role="assistant", text=turn.reply,
            sources=list(turn.sources), citations=list(turn.citations),
        ))
        session.memory = turn.memory
        store.save(session)

    final_memory = session.memory
    goal_kept = _goal_kept(initial_goal, final_memory.goal)
    memory_grown = bool(
        final_memory.constraints or final_memory.clarifications or final_memory.terms
    )
    passed = all_with_sources and goal_kept and memory_grown
    return ScenarioReport(
        name=name,
        turns=len(session.messages),
        all_with_sources=all_with_sources,
        goal_kept=goal_kept,
        memory_grown=memory_grown,
        passed=passed,
        final_memory=final_memory.to_dict(),
    )


async def run_all_scenarios(
    service: ChatService, store: SessionStore, scenarios_dir: str | Path
) -> list[ScenarioReport]:
    reports = []
    for path in sorted(Path(scenarios_dir).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        reports.append(await run_scenario(
            service, store, data["name"], data["goal"], data["messages"]
        ))
    return reports
