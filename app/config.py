from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    app_version: str = "dev"
    log_level: str = "INFO"
    database_url: str
    api_key: str = ""
    tz_name: str = "Asia/Kolkata"


@lru_cache
def get_settings() -> Settings:
    return Settings()
