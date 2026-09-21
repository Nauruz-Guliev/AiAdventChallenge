from functools import lru_cache
from pathlib import Path

from app.application.agent import Agent
from app.application.ports.chat_repository import ChatRepository
from app.domain.models import UsageConfig
from app.infrastructure.deepseek_gateway import DeepSeekGateway
from app.infrastructure.json_invariant_repository import JsonInvariantRepository
from app.infrastructure.json_memory_repository import JsonMemoryRepository
from app.infrastructure.json_profile_repository import JsonProfileRepository
from app.infrastructure.json_task_repository import JsonTaskRepository
from app.infrastructure.settings import Settings
from app.infrastructure.token_counter import TiktokenCounter


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_repository() -> JsonMemoryRepository:
    settings = get_settings()
    return JsonMemoryRepository(
        chats_dir=Path(settings.chats_dir),
        long_term_path=Path(settings.long_term_file),
        candidates_path=Path(settings.candidates_file),
    )


@lru_cache
def get_profile_repository() -> JsonProfileRepository:
    settings = get_settings()
    return JsonProfileRepository(profiles_path=Path(settings.profiles_file))


@lru_cache
def get_task_repository() -> JsonTaskRepository:
    settings = get_settings()
    return JsonTaskRepository(state_path=Path(settings.task_state_file))


@lru_cache
def get_invariant_repository() -> JsonInvariantRepository:
    settings = get_settings()
    return JsonInvariantRepository(path=Path(settings.invariants_file))


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
        long_term_max_per_category=settings.long_term_max_per_category,
        long_term_max_item_chars=settings.long_term_max_item_chars,
        profile_max_constraints=settings.profile_max_constraints,
        profile_max_item_chars=settings.profile_max_item_chars,
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
        candidates_enabled=settings.candidates_enabled,
        profiles=get_profile_repository(),
        task_repository=get_task_repository(),
        invariants=get_invariant_repository(),
    )