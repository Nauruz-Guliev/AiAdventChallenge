from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = ""
    telegram_api_ip: str = ""

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4:12b"
    ollama_num_ctx: int = 8192
    ollama_keep_alive: str = "10m"
    think_default: bool = False

    index_path: str = "../../day21/index/structure.json"
    embedder: str = "sentence"
    embedder_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    top_k_pre: int = 30
    top_k_post: int = 6
    min_sim: float = 0.35
    no_answer_min_score: float = 0.60

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    eval_runs: int = 3
    eval_questions_path: str = "app/data/eval_questions.json"

    history_max_messages: int = 20
    history_max_chars: int = 12000
    request_timeout: float = 300.0
    data_dir: str = "data"

    def ollama_options(self) -> dict:
        return {"num_ctx": self.ollama_num_ctx}
