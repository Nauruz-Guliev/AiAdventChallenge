from functools import lru_cache
from pathlib import Path

from app.application.ports.chat_repository import ChatRepository
from app.application.agent import Agent
from app.infrastructure.deepseek_gateway import DeepSeekGateway
from app.infrastructure.json_chat_repository import JsonChatRepository
from app.infrastructure.settings import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_repository() -> JsonChatRepository:
    settings = get_settings()
    return JsonChatRepository(Path(settings.context_file))


def get_agent() -> Agent:
    settings = get_settings()
    gateway = DeepSeekGateway(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )
    repository: ChatRepository = get_repository()
    return Agent(gateway, repository=repository, model=settings.deepseek_model)
