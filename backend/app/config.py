from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # Диплом/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql+asyncpg://nutriagent:nutriagent@localhost:5433/nutriagent"
    DB_HOST: str | None = None
    DB_PORT: int = 5432
    DB_NAME: str = "nutriagent"
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None
    REDIS_URL: str = "redis://localhost:6379/0"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_MODEL_NAME: str = "openai/gpt-4o"
    LLM_TIMEOUT_SEC: int = 60
    LLM_MAX_OUTPUT_TOKENS: int = 1200
    LLM_MAX_RETRIES: int = 4
    LLM_CONTEXT_RECIPE_LIMIT: int = 18
    AGENT_CLI_MIN_CONTEXT_RECIPE_LIMIT: int = 60
    LLM_RETRY_HISTORY_LIMIT: int = 1
    LLM_RETRY_RESPONSE_PREVIEW_CHARS: int = 600
    EMBEDDING_MODEL_NAME: str = "openai/text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_MAX_RETRIES: int = 3
    RAG_VECTOR_CANDIDATE_LIMIT: int = 200
    RAG_VECTOR_WEIGHT: float = 0.8
    RAG_PREFERENCE_WEIGHT: float = 0.2
    CATALOG_SOURCE_FETCH_TIMEOUT_SEC: int = 20
    CATALOG_SOURCE_MAX_BYTES: int = 60000
    CATALOG_SOURCE_TEXT_CHAR_LIMIT: int = 6000
    CATALOG_ALLOWED_SOURCE_DOMAINS: str = ""
    CATALOG_MAX_SOURCES_PER_JOB: int = 10
    CATALOG_AGENT_MAX_TOOL_ROUNDS: int = 4
    ADMIN_EMAILS: str = ""
    SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    AGENT_TOOL_USE_ENABLED: bool = False
    AGENT_MAX_LLM_CALLS: int = Field(default=10, ge=1)
    AGENT_MAX_SEARCH_CALLS: int = Field(default=5, ge=1, le=20)

    DEBUG: bool = False

    DEV_MODE: bool = False
    DEV_USER_EMAIL: str = "demo@example.com"
    DEV_USER_PASSWORD: str = "demo123456"

    @property
    def database_url(self) -> str:
        if self.DB_HOST and self.DB_USER and self.DB_PASSWORD:
            return URL.create(
                "postgresql+asyncpg",
                username=self.DB_USER,
                password=self.DB_PASSWORD,
                host=self.DB_HOST,
                port=self.DB_PORT,
                database=self.DB_NAME,
            ).render_as_string(hide_password=False)
        return self.DATABASE_URL

    @property
    def database_url_sync(self) -> str:
        return self.database_url.replace("+asyncpg", "")

    @property
    def admin_emails(self) -> set[str]:
        return {email.strip().lower() for email in self.ADMIN_EMAILS.split(",") if email.strip()}


settings = Settings()
