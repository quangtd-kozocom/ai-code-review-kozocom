from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    APP_URL: str | None = None

    # GitHub
    GITHUB_APP_ID: int
    GITHUB_PRIVATE_KEY: str
    GITHUB_WEBHOOK_SECRET: str

    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_DEFAULT_MODEL: str = "xiaomi/mimo-v2-flash:free"

    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None

    # Redis (Celery)
    REDIS_URL: str

    # Database - Neon PostgreSQL
    DATABASE_URL: str | None = None

    # Cache - Upstash Redis
    UPSTASH_REDIS_URL: str | None = None

    # Config System
    CONFIG_CACHE_TTL: int = 300  # 5 minutes

    # Slack
    SLACK_BOT_TOKEN: str | None = None
    SLACK_CHANNEL: str = "#pr-reviews"

    # Sentry
    SENTRY_DSN: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
