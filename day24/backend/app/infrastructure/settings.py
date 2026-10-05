from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    llm_provider: str = "deepseek"
    index_path: str = "../../day21/index/structure.json"
    top_k: int = 8
    k_pre: int = 30
    k_post: int = 8
    min_sim: float = 0.35
    w_sim: float = 0.6
    w_lex: float = 0.3
    w_head: float = 0.1
    rewrite_enabled: bool = True
    min_quote_len: int = 24
    no_answer_min_score: float = 0.60
    eval_questions_path: str = "app/data/eval_questions.json"
    eval_report_path: str = "data/eval_report.json"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
