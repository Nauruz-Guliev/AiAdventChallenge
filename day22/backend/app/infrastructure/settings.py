from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    llm_provider: str = "deepseek"
    index_path: str = "../../day21/index/structure.json"
    top_k: int = 8
    eval_questions_path: str = "app/data/eval_questions.json"
    eval_report_path: str = "data/eval_report.json"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
