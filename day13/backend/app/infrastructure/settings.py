from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    chats_dir: str = "data/chats"
    long_term_file: str = "data/long_term.json"
    candidates_file: str = "data/candidates.json"
    profiles_file: str = "data/profiles.json"
    context_limit_tokens: int = 8000
    input_price_per_million: float = 0.30
    output_price_per_million: float = 1.20
    long_term_max_per_category: int = 50
    long_term_max_item_chars: int = 500
    candidates_enabled: bool = True
    profile_max_constraints: int = 20
    profile_max_item_chars: int = 300

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")