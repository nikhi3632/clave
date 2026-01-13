from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Supabase
    supabase_url: str
    supabase_anon_key: str

    # Anthropic
    anthropic_api_key: str
    llm_model: str = "claude-sonnet-4-20250514"

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Server
    debug: bool = False

    # Timeouts (seconds)
    api_timeout: int = 30
    drill_down_timeout: int = 15

    # Cache TTLs (seconds)
    date_range_cache_ttl: int = 300  # 5 minutes
    schema_cache_ttl: int = 600  # 10 minutes

    # Retry settings
    db_max_retries: int = 2
    db_retry_delay: float = 0.5
    llm_max_retries: int = 3
    llm_initial_retry_delay: float = 1.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
