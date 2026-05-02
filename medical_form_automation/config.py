"""Application configuration loaded from environment / .env."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: SecretStr
    llama_parse_api_key: SecretStr

    gemini_model: str = "models/gemini-3.0-flash"
    gemini_temperature: float = 0.1

    log_level: str = "INFO"
    log_json: bool = True

    request_timeout_s: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MFA_",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
