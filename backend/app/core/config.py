"""Application configuration, loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- General ---
    app_name: str = "Fareeq Personal AI Team"
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    auth_required: bool = False
    auth_secret: str = Field(default="", repr=False)
    auth_access_keys: dict[str, str] = Field(default_factory=dict, repr=False)
    session_seconds: int = Field(default=604800, ge=60, le=2592000)
    llm_timeout_seconds: float = Field(default=35, ge=1, le=120)
    llm_reasoning_effort: str = "low"
    account_requests_per_minute: int = Field(default=6, ge=1)
    account_daily_token_budget: int = Field(default=60000, ge=1)
    # Tokens per account per UTC day: charged up front from a high estimate,
    # then trued up to what the provider reports. See app/core/usage.py.
    memory_timeout_seconds: float = Field(default=8, ge=1, le=30)

    # --- Documents (RAG) ---
    #: Upload files to an agent and have it answer from them. See docs/rag.md.
    documents_enabled: bool = True
    documents_per_user: int = Field(default=5, ge=0, le=50)
    document_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    #: Most text kept from one document, after extraction.
    document_max_chars: int = Field(default=400_000, ge=1000)
    #: Characters of retrieved text added to a turn (~4 chars a token).
    rag_context_chars: int = Field(default=4000, ge=500, le=20000)
    #: Where the ONNX embedding model lives. Empty or missing = keyword search only.
    embedding_model_dir: str = Field(default="models/multilingual-e5-small")
    #: Relevance gate for multilingual-e5 cosine similarity: a top score this high
    #: counts on its own; one above the soft level counts when it beats the
    #: median of the person's passages by the margin. Calibrated on the eval set.
    rag_min_similarity: float = Field(default=0.84, ge=0.0, le=1.0)
    rag_soft_similarity: float = Field(default=0.79, ge=0.0, le=1.0)
    rag_similarity_margin: float = Field(default=0.05, ge=0.0, le=1.0)
    #: Seconds a document may take to parse in its sandboxed subprocess.
    document_parse_seconds: float = Field(default=30, ge=1, le=300)
    #: Extra seconds for a photo or scanned PDF read with OCR (up to 15 pages).
    ocr_parse_seconds: float = Field(default=150, ge=0, le=600)

    # --- Voice ---
    #: Speech to text for the mic button (Groq's free Whisper endpoint). Needs
    #: LLM_PROVIDER=groq; audio is sent for transcription and never stored.
    voice_enabled: bool = True
    transcribe_model: str = Field(default="whisper-large-v3-turbo")
    voice_max_bytes: int = Field(default=4 * 1024 * 1024, ge=1024)
    #: Transcriptions per account per UTC day. Groq limits audio separately.
    voice_per_day: int = Field(default=60, ge=0)

    # --- Features ---
    #: Ask My Team (POST /api/team/ask). Off for the initial release: no screen
    #: calls it yet, and it is the most expensive route — up to five specialists
    #: plus a synthesis per request against a shared free quota. The
    #: implementation is kept and tested; set TEAM_ENABLED=true to switch it on
    #: once a UI exists. See docs/launch-fixes.md.
    team_enabled: bool = False
    #: Open signup (POST /api/auth/signup and the /signup page). Off until you
    #: choose to open the doors: an invite-only beta keeps provisioning accounts
    #: by hand, and turning this on is the public-launch step. SIGNUP_ENABLED=true.
    signup_enabled: bool = False

    # --- Operations ---
    #: Accounts allowed to see the monitoring dashboard. It shows every
    #: account's usage, so it is not for every invitee.
    admin_accounts: list[str] = Field(default_factory=list)
    #: Alerting. Any channel left blank is simply not used; with none set,
    #: alerting is off. See app/core/alerts.py.
    alert_webhook_url: str = Field(default="", repr=False)
    alert_telegram_bot_token: str = Field(default="", repr=False)
    alert_telegram_chat_id: str = Field(default="", repr=False)
    #: Alert once this many unhandled errors have happened since start, then
    #: again on each further multiple. Low, because on a private deployment
    #: any unhandled error is worth a look.
    alert_error_threshold: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def validate_security(self):
        if self.environment == "production":
            if self.debug or not self.auth_required:
                raise ValueError("Production requires DEBUG=false and AUTH_REQUIRED=true")
            if not self.frontend_url.startswith("https://"):
                raise ValueError("Production FRONTEND_URL must use HTTPS")
            # Otherwise a missing LLM_PROVIDER would serve the offline preview
            # model to invitees while every health check reported ok.
            if self.llm_provider.lower().strip() in ("", "mock", "none"):
                raise ValueError("Production requires a real LLM_PROVIDER, not the mock model")
            if not self.llm_api_key:
                raise ValueError("Production requires LLM_API_KEY")
        if self.auth_required:
            # Access keys are optional now: accounts can also sign in with a
            # password. The signing secret is what every session rests on.
            if len(self.auth_secret) < 32:
                raise ValueError("Authentication requires a strong AUTH_SECRET")
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
    #: Model for the per-message memory call. Empty uses the agent's own model.
    #: A smaller one is cheaper, and on Groq's free tier a different model also
    #: draws on its own daily token limit rather than the chat model's.
    memory_model: str = Field(default="")

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
