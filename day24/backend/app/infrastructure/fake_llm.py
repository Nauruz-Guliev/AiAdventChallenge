from __future__ import annotations

import json


class FakeLLM:
    def __init__(self, answer: str = "FAKE answer", judge_score: float = 1.0):
        self.answer = answer
        self.judge_score = judge_score

    async def complete(self, messages: list[dict[str, str]]) -> str:
        system = messages[0]["content"] if messages and messages[0].get("role") == "system" else ""
        if system.startswith("JUDGE"):
            return json.dumps({"score": self.judge_score})
        return self.answer
