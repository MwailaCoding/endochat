"""Application configuration using Pydantic Settings."""

from typing import Optional
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "EndoChat API"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/endochat"
    db_pool_min_size: int = 5
    db_pool_max_size: int = 20

    # Redis Cache
    redis_url: Optional[str] = None
    cache_ttl_seconds: int = 86400  # 24 hours
    cache_enabled: bool = True

    # API Keys
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-3.5-turbo"
    openai_enabled: bool = True

    pubmed_api_key: Optional[str] = None
    pubmed_email: str = "developer@endochat.org"

    openfda_api_key: Optional[str] = None

    drugbank_api_key: Optional[str] = None

    # API Settings
    api_timeout: int = 10
    api_max_retries: int = 3

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_period: int = 60  # seconds

    # CORS
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Cloudinary (Image Storage)
    cloudinary_cloud_name: Optional[str] = None
    cloudinary_api_key: Optional[str] = None
    cloudinary_api_secret: Optional[str] = None

    # HTML-to-Image API
    hcti_api_user_id: Optional[str] = None
    hcti_api_key: Optional[str] = None

    # Feature Flags
    enable_stories: bool = True
    enable_groups: bool = True
    enable_candles: bool = True
    enable_insights: bool = True
    enable_sharing: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins string into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_openai_available(self) -> bool:
        """Check if OpenAI is configured and enabled."""
        return bool(self.openai_api_key) and self.openai_enabled

    @property
    def is_redis_available(self) -> bool:
        """Check if Redis is configured."""
        return bool(self.redis_url)

    @property
    def is_cloudinary_available(self) -> bool:
        """Check if Cloudinary is configured."""
        return bool(
            self.cloudinary_cloud_name
            and self.cloudinary_api_key
            and self.cloudinary_api_secret
        )

    @property
    def is_hcti_available(self) -> bool:
        """Check if HTML-to-Image API is configured."""
        return bool(self.hcti_api_user_id and self.hcti_api_key)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
