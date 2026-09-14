from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    context_file: str = "data/chats.json"
    context_limit_tokens: int = 8000
    input_price_per_million: float = 0.30
    output_price_per_million: float = 1.20

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
