from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BAITEREK_", extra="ignore")
    database_url: str = "postgresql+asyncpg://baiterek:baiterek@postgres/baiterek"

    # Демо-режим «без логинов» (ENV BAITEREK_OPEN_ACCESS=1). На публичном конкурсном
    # стенде любой посетитель работает без входа: неизвестный X-User-Id автоматически
    # заводится как пользователь, а ролевые гейты (/create, админ-действия) не проверяются
    # — так жюри и гости пробуют и клиентский, и административный контур без учётки.
    # По умолчанию ВЫКЛ: юнит-тесты гоняют штатную auth/RBAC-логику. Включается только
    # на стенде. Данные синтетические, периметр закрыт (SECURITY: порты на 127.0.0.1).
    open_access: bool = False

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
