from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000

    ollama_base_url: str = "http://localhost:11434"
    default_model: str = "gemma4:12b"
    keep_alive: str = "10m"
    request_timeout: float = 300.0

    api_keys: str = ""
    require_api_key: bool = False

    num_ctx: int = 8192
    max_tokens_default: int = 512
    max_tokens_limit: int = 2048

    rate_limit_per_minute: int = 30
    rate_limit_burst: int = 10

    max_concurrency: int = 1
    max_queue: int = 8

    frontend_dir: str = "frontend"

    def key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}
