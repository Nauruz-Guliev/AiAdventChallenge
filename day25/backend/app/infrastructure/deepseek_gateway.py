from __future__ import annotations

from httpx import Timeout
from openai import AsyncOpenAI

from app.domain.models import LLMGatewayError


class DeepSeekGateway:
    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
        client: AsyncOpenAI | None = None,
    ):
        self._model = model
        self._client = client or AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=Timeout(connect=15.0, read=90.0, write=60.0, pool=15.0),
            max_retries=1,
        )

    async def complete(self, messages: list[dict[str, str]]) -> str:
        try:
            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.3,
            )
        except Exception as error:
            raise LLMGatewayError(str(error)) from error
        text = (completion.choices[0].message.content or "").strip()
        if not text:
            raise LLMGatewayError("Провайдер вернул пустой ответ")
        return text
