from __future__ import annotations

import json


class FakeLLM:
    def __init__(
        self,
        answer: str = "FAKE answer [1]",
        memory: dict | None = None,
        rewrite: str = "ktor client setup",
        judge_score: float = 1.0,
    ):
        self.answer = answer
        self.memory = memory or {"goal": "", "clarifications": [], "constraints": [], "terms": []}
        self.rewrite = rewrite
        self.judge_score = judge_score
        self.calls: list[list[dict]] = []

    async def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        system = messages[0]["content"] if messages and messages[0].get("role") == "system" else ""
        if system.startswith("REWRITE"):
            return self.rewrite
        if system.startswith("MEMORY"):
            return json.dumps(self.memory, ensure_ascii=False)
        if system.startswith("JUDGE"):
            return json.dumps({"score": self.judge_score})
        return self.answer
