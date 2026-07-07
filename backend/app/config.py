from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BAITEREK_", extra="ignore")
    database_url: str = "postgresql+asyncpg://baiterek:baiterek@postgres/baiterek"

@lru_cache
def settings() -> Settings:
    return Settings()
