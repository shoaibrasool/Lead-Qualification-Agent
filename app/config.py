from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(os.path.dirname(BASE_DIR), ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    gemini_api_key: SecretStr
    gemini_model: str = "gemini-2.5-flash-lite"
    calcom_api_key: SecretStr
    calcom_event_type_id: int
    slack_webhook_url: SecretStr
    mongodb_connection_string: SecretStr

    auto_book_threshold: int = Field(default=70, ge=0, le=100)
    flag_followup_threshold: int = Field(default=40, ge=0, le=100)
    max_conversation_turns: int = Field(default=8, ge=1, le=100)

    app_env: Literal["dev", "staging", "prod"] = "dev"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
