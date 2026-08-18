"""Centralized application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"
    log_json: bool = True

    api_keys: str = "local-dev-key"

    database_url: str = "postgresql+asyncpg://copilot:copilot@localhost:5432/copilot"

    redis_url: str = "redis://localhost:6379/0"

    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    github_token: str = ""
    github_api_url: str = "https://api.github.com"

    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_enabled: bool = True

    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "ai-devops-copilot"

    @property
    def api_key_list(self) -> list[str]:
        return [key.strip() for key in self.api_keys.split(",") if key.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
