from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)

from app.domain.models import (
    AuthenticationGatewayError,
    ChatMessage,
    ContextLimitExceeded,
    GatewayTimeoutError,
    LLMGatewayError,
    LLMResponse,
    RateLimitGatewayError,
    TokenUsage,
)


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
            timeout=30,
            max_retries=0,
        )

    async def complete(self, messages: list[ChatMessage]) -> LLMResponse:
        request_messages = [
            {"role": message.role, "content": message.content}
            for message in messages
        ]
        try:
            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=request_messages,
                temperature=0.7,
            )
        except AuthenticationError as error:
            raise AuthenticationGatewayError from error
        except RateLimitError as error:
            raise RateLimitGatewayError from error
        except APITimeoutError as error:
            raise GatewayTimeoutError from error
        except APIConnectionError as error:
            raise LLMGatewayError from error
        except BadRequestError as error:
            if _is_context_length_error(error):
                raise ContextLimitExceeded() from error
            raise LLMGatewayError from error
        except Exception as error:
            raise LLMGatewayError from error

        text = (completion.choices[0].message.content or "").strip()
        if not text:
            raise LLMGatewayError("Provider returned an empty response")

        usage = getattr(completion, "usage", None)
        if usage is None:
            raise LLMGatewayError("Provider returned no token usage")

        return LLMResponse(
            text=text,
            model=completion.model or self._model,
            usage=TokenUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            ),
        )


def _is_context_length_error(error: BadRequestError) -> bool:
    body = error.body if isinstance(error.body, dict) else {}
    inner = body.get("error") if isinstance(body.get("error"), dict) else {}
    code = inner.get("code")
    return code == "context_length_exceeded" or "context_length_exceeded" in str(error)
