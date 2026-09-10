"""Application configuration, loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- General ---
    app_name: str = "Modeer Personal AI Team"
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    auth_required: bool = False
    auth_secret: str = Field(default="", repr=False)
    auth_access_keys: dict[str, str] = Field(default_factory=dict, repr=False)
    session_seconds: int = Field(default=604800, ge=60, le=2592000)
    llm_timeout_seconds: float = Field(default=35, ge=1, le=120)
    llm_reasoning_effort: str = "low"
    memory_timeout_seconds: float = Field(default=8, ge=1, le=30)

    @model_validator(mode="after")
    def validate_security(self):
        if self.environment == "production":
            if self.debug or not self.auth_required:
                raise ValueError("Production requires DEBUG=false and AUTH_REQUIRED=true")
            if not self.frontend_url.startswith("https://"):
                raise ValueError("Production FRONTEND_URL must use HTTPS")
        if self.auth_required:
            if len(self.auth_secret) < 32 or not self.auth_access_keys:
                raise ValueError(
                    "Authentication requires a strong AUTH_SECRET and AUTH_ACCESS_KEYS"
                )
            if any(
                len(v) != 64 or any(c not in "0123456789abcdef" for c in v)
                for v in self.auth_access_keys.values()
            ):
                raise ValueError("Access keys must be SHA-256 hex digests")
        return self

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
    # "auto" -> LLM extraction when a real provider is configured, else rules.
    # Force with "llm" or "rules".
    memory_extraction: str = Field(default="auto")

    @property
    def use_llm_extraction(self) -> bool:
        mode = self.memory_extraction.lower().strip()
        if mode == "llm":
            return True
        if mode == "rules":
            return False
        return self.llm_provider.lower().strip() not in ("", "mock", "none")

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
