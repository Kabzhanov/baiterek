from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BAITEREK_", extra="ignore")
    database_url: str = "postgresql+asyncpg://baiterek:baiterek@postgres/baiterek"

    # AI layer (SPEC.md §7.3 "техконтур"). `llm_provider`/`llm_daily_limit` follow the
    # app's usual `BAITEREK_` prefix; `anthropic_api_key` intentionally does NOT
    # (`validation_alias` overrides the prefix) because the task spec names the raw
    # `ANTHROPIC_API_KEY` env var explicitly, matching Anthropic's own SDK convention.
    llm_provider: str = "mock"  # ENV BAITEREK_LLM_PROVIDER: "mock" | "anthropic"
    llm_daily_limit: int = 500  # ENV BAITEREK_LLM_DAILY_LIMIT — audit_log ai_call rows/day cap
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    anthropic_model: str = "claude-sonnet-5"  # ENV BAITEREK_ANTHROPIC_MODEL


@lru_cache
def settings() -> Settings:
    return Settings()
