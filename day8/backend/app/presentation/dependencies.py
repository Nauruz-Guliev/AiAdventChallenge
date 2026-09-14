from functools import lru_cache
from pathlib import Path

from app.application.ports.chat_repository import ChatRepository
from app.application.agent import Agent
from app.domain.models import UsageConfig
from app.infrastructure.deepseek_gateway import DeepSeekGateway
from app.infrastructure.json_chat_repository import JsonChatRepository
from app.infrastructure.settings import Settings
from app.infrastructure.token_counter import TiktokenCounter


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_repository() -> JsonChatRepository:
    settings = get_settings()
    return JsonChatRepository(Path(settings.context_file))


@lru_cache
def get_token_counter() -> TiktokenCounter:
    return TiktokenCounter()


@lru_cache
def get_usage_config() -> UsageConfig:
    settings = get_settings()
    return UsageConfig(
        context_limit_tokens=settings.context_limit_tokens,
        input_price_per_million=settings.input_price_per_million,
        output_price_per_million=settings.output_price_per_million,
    )


def get_agent() -> Agent:
    settings = get_settings()
    gateway = DeepSeekGateway(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )
    repository: ChatRepository = get_repository()
    return Agent(
        gateway,
        repository=repository,
        counter=get_token_counter(),
        config=get_usage_config(),
        model=settings.deepseek_model,
    )
