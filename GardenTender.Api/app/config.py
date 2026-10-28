from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    auth0_domain: str = ""
    auth0_audience: str = ""
    # Prefix of custom claims added by the Auth0 Action, e.g. "https://gardentender/" -> "https://gardentender/email".
    auth0_claims_namespace: str = ""
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
    garden_retention_days: int = 15  # soft-deleted gardens are restorable this long, then purged
    invite_ttl_days: int = 7
    qr_invite_ttl_minutes: int = 15
    # Public origin used in emailed and QR links (App Links). Locally: an ngrok static domain.
    public_base_url: str = "http://localhost:8000"
    email_backend: str = "console"  # only console until a provider is chosen
    # Mount development-only routes (app/routers/debug.py). Never enable in production.
    debug_endpoints: bool = False
    # Android App Links verification (/.well-known/assetlinks.json)
    android_package: str = "com.gardentender"
    android_cert_sha256: list[str] = []


@lru_cache
def get_settings() -> Settings:
    return Settings()
