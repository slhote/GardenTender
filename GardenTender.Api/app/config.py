from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    auth0_domain: str = ""
    auth0_audience: str = ""
    anthropic_api_key: str = ""
    llm_provider: str = "claude"  # claude | ollama
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "claude-haiku-5-5"
    # Models the app may select per request when llm_provider is ollama (the first is the app's default).
    ollama_models: list[str] = ["gemma4", "qwen3.5:4b", "qwen2.5:3b"]
    max_tool_steps: int = 5
    db_pool_size: int = 5
    db_max_overflow: int = 5
    database_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
