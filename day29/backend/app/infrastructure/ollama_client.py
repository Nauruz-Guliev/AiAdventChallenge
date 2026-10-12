from __future__ import annotations

import json
from typing import AsyncIterator, Optional

import httpx

from app.domain.models import ChatMessage, GenerationStats
from app.ports.llm import Completion, ModelInfo, OllamaUnavailable, StreamDelta, StreamDone


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 300.0,
        keep_alive: str = "10m",
        default_options: Optional[dict] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._keep_alive = keep_alive
        self._default_options = default_options or {}
        self._client = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def health(self) -> bool:
        try:
            r = await self._client.get(f"{self._base_url}/api/version", timeout=5.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def list_models(self) -> list[ModelInfo]:
        try:
            r = await self._client.get(f"{self._base_url}/api/tags")
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise OllamaUnavailable(str(e)) from e
        out: list[ModelInfo] = []
        for m in r.json().get("models", []):
            out.append(
                ModelInfo(
                    name=m.get("name", ""),
                    parameter_size=(m.get("details") or {}).get("parameter_size", ""),
                )
            )
        return out

    def _payload(self, messages, think, options, stream, model=None):
        return {
            "model": model or self._model,
            "messages": [m.to_ollama() for m in messages],
            "stream": stream,
            "keep_alive": self._keep_alive,
            "think": think,
            "options": {**self._default_options, **(options or {})},
        }

    async def tags(self) -> list[dict]:
        try:
            r = await self._client.get(f"{self._base_url}/api/tags")
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise OllamaUnavailable(str(e)) from e
        return r.json().get("models", [])

    async def ps(self) -> list[dict]:
        try:
            r = await self._client.get(f"{self._base_url}/api/ps")
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise OllamaUnavailable(str(e)) from e
        return r.json().get("models", [])

    async def complete(
        self, messages, think: bool = False, options=None, model=None
    ) -> Completion:
        payload = self._payload(messages, think, options, stream=False, model=model)
        try:
            r = await self._client.post(f"{self._base_url}/api/chat", json=payload)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise OllamaUnavailable(str(e)) from e
        obj = r.json()
        msg = obj.get("message") or {}
        text = (msg.get("content") or "").strip()
        if not text:
            raise OllamaUnavailable("Локальная модель вернула пустой ответ")
        return Completion(
            text=text,
            stats=GenerationStats(
                model=obj.get("model", self._model),
                prompt_tokens=obj.get("prompt_eval_count", 0) or 0,
                completion_tokens=obj.get("eval_count", 0) or 0,
                eval_duration_ns=obj.get("eval_duration", 0) or 0,
                total_duration_ns=obj.get("total_duration", 0) or 0,
                load_duration_ns=obj.get("load_duration", 0) or 0,
            ),
        )

    async def stream_chat(
        self, messages, think: bool = False, options=None, model=None
    ) -> AsyncIterator:
        payload = self._payload(messages, think, options, stream=True, model=model)
        try:
            async with self._client.stream("POST", f"{self._base_url}/api/chat", json=payload) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise OllamaUnavailable(
                        f"HTTP {resp.status_code}: {body[:200].decode('utf-8', 'ignore')}"
                    )
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = obj.get("message") or {}
                    if msg.get("thinking"):
                        yield StreamDelta(kind="thinking", text=msg["thinking"])
                    if msg.get("content"):
                        yield StreamDelta(kind="content", text=msg["content"])
                    if obj.get("done"):
                        yield StreamDone(
                            stats=GenerationStats(
                                model=obj.get("model", self._model),
                                prompt_tokens=obj.get("prompt_eval_count", 0) or 0,
                                completion_tokens=obj.get("eval_count", 0) or 0,
                                eval_duration_ns=obj.get("eval_duration", 0) or 0,
                                total_duration_ns=obj.get("total_duration", 0) or 0,
                                load_duration_ns=obj.get("load_duration", 0) or 0,
                            )
                        )
        except httpx.HTTPError as e:
            raise OllamaUnavailable(str(e)) from e
