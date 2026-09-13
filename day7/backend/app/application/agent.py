from time import perf_counter

from app.application.ports.llm_gateway import LLMGateway
from app.domain.models import AgentResult, AgentStage, ChatMessage, InvalidUserMessage


SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer in the same language as the user. "
    "Be concise, clear, and complete. Never reveal private hidden chain-of-thought; "
    "give a short useful summary instead if the user asks how you reasoned."
)
MAX_MESSAGE_LENGTH = 4000


class Agent:
    def __init__(self, gateway: LLMGateway, model: str = "deepseek-chat"):
        self._gateway = gateway
        self._model = model

    async def run(self, user_text: str) -> AgentResult:
        if not isinstance(user_text, str):
            raise InvalidUserMessage("Message must be a string")

        message = user_text.strip()
        if not message:
            raise InvalidUserMessage("Message cannot be blank")
        if len(message) > MAX_MESSAGE_LENGTH:
            raise InvalidUserMessage(
                f"Message must be shorter than {MAX_MESSAGE_LENGTH} characters"
            )

        started_at = perf_counter()
        response = await self._gateway.complete([
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=message),
        ])

        return AgentResult(
            answer=response.text.strip(),
            model=response.model or self._model,
            duration_ms=round((perf_counter() - started_at) * 1000),
            stages=[
                AgentStage(name="UI", status="completed"),
                AgentStage(name="Agent", status="completed"),
                AgentStage(name="DeepSeek API", status="completed"),
            ],
        )
