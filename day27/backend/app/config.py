from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4:12b"
    ollama_num_ctx: int = 8192
    ollama_keep_alive: str = "10m"
    system_prompt: str = "Ты — полезный ассистент. Отвечай кратко и по делу."
    history_max_messages: int = 20
    history_max_chars: int = 12000
    request_timeout: float = 300.0
    data_dir: str = "data"
    telegram_api_ip: str = ""

    def ollama_options(self) -> dict:
        return {"num_ctx": self.ollama_num_ctx}
