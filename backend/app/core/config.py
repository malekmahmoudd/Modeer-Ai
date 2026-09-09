"""Application configuration, loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- General ---
    app_name: str = "Modeer Personal AI Team"
    environment: str = Field(default="development")
    debug: bool = Field(default=True)

    # --- Database ---
    # Defaults to a local SQLite file so the API runs with zero setup.
    # For the real stack use PostgreSQL, e.g.:
    #   postgresql+psycopg://modeer:modeer@localhost:5432/modeer
    database_url: str = Field(default="sqlite+pysqlite:///./modeer.db")

    # --- CORS / frontend ---
    frontend_url: str = Field(default="http://localhost:3000")

    # --- LLM provider ---
    # provider: "mock" (default, no key needed), "anthropic", or "openai".
    llm_provider: str = Field(default="mock")
    llm_api_key: str = Field(default="")
    llm_model: str = Field(default="claude-sonnet-5")
    llm_base_url: str = Field(default="")
    llm_max_tokens: int = Field(default=1024)
    llm_temperature: float = Field(default=0.6)

    # --- Memory extraction ---
    # When false, sensitive-looking candidates are dropped instead of stored.
    memory_store_sensitive: bool = Field(default=False)
    memory_min_confidence: float = Field(default=0.55)

    @property
    def cors_origins(self) -> list[str]:
        raw = self.frontend_url
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
