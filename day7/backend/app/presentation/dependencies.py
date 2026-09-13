from functools import lru_cache

from app.application.agent import Agent
from app.infrastructure.deepseek_gateway import DeepSeekGateway
from app.infrastructure.settings import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_agent() -> Agent:
    settings = get_settings()
    gateway = DeepSeekGateway(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )
    return Agent(gateway, model=settings.deepseek_model)
