from __future__ import annotations

import json
from typing import AsyncIterator, Optional

import httpx

from app.domain.models import (
    ChatMessage,
    Completion,
    ModelInfo,
    StreamDelta,
    StreamDone,
    UpstreamUnavailable,
    Usage,
)


class OllamaGateway:
    def __init__(
        self,
        base_url: str,
        *,
        keep_alive: str = "10m",
        timeout: float = 300.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._keep_alive = keep_alive
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _options(
        self,
        temperature: float | None,
        max_tokens: int | None,
        num_ctx: int | None,
    ) -> dict:
        options: dict = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if num_ctx is not None:
            options["num_ctx"] = num_ctx
        return options

    def _payload(self, messages, stream, *, model, temperature, max_tokens, num_ctx) -> dict:
        return {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
            "keep_alive": self._keep_alive,
            "think": False,
            "options": self._options(temperature, max_tokens, num_ctx),
        }

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
            raise UpstreamUnavailable(f"Ollama недоступен: {e}") from e
        return [
            ModelInfo(
                id=m.get("name", ""),
                parameter_size=(m.get("details") or {}).get("parameter_size", ""),
            )
            for m in r.json().get("models", [])
        ]

    async def loaded_models(self) -> list[dict]:
        try:
            r = await self._client.get(f"{self._base_url}/api/ps")
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise UpstreamUnavailable(f"Ollama недоступен: {e}") from e
        return r.json().get("models", [])

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        num_ctx: int | None = None,
    ) -> Completion:
        payload = self._payload(
            messages,
            False,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            num_ctx=num_ctx,
        )
        try:
            r = await self._client.post(f"{self._base_url}/api/chat", json=payload)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise UpstreamUnavailable(f"Ollama недоступен: {e}") from e
        obj = r.json()
        text = ((obj.get("message") or {}).get("content") or "").strip()
        usage = Usage.of(obj.get("prompt_eval_count", 0) or 0, obj.get("eval_count", 0) or 0)
        return Completion(text=text, model=obj.get("model", model or ""), usage=usage)

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        num_ctx: int | None = None,
    ) -> AsyncIterator[StreamDelta | StreamDone]:
        payload = self._payload(
            messages,
            True,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            num_ctx=num_ctx,
        )
        try:
            async with self._client.stream(
                "POST", f"{self._base_url}/api/chat", json=payload
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise UpstreamUnavailable(
                        f"Ollama HTTP {resp.status_code}: {body[:200].decode('utf-8', 'ignore')}"
                    )
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    content = (obj.get("message") or {}).get("content")
                    if content:
                        yield StreamDelta(text=content)
                    if obj.get("done"):
                        yield StreamDone(
                            model=obj.get("model", model or ""),
                            usage=Usage.of(
                                obj.get("prompt_eval_count", 0) or 0,
                                obj.get("eval_count", 0) or 0,
                            ),
                        )
        except httpx.HTTPError as e:
            raise UpstreamUnavailable(f"Ollama недоступен: {e}") from e
