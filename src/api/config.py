from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """
    Twelve-Factor App: Factor III - Config in the Environment.
    Centralized configuration using Pydantic Settings.
    Reads environment variables with sensible local defaults.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Metadata
    APP_NAME: str = "Chirpify Analytics Ingestion Service"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development, staging, production
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # API Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # AWS / LocalStack Configuration
    AWS_REGION: str = "us-east-1"
    AWS_ENDPOINT_URL: Optional[str] = None  # Set to http://localhost:4566 for LocalStack
    SQS_QUEUE_URL: str = "http://localhost:4566/000000000000/chirpify-events-queue"
    USE_MOCK_QUEUE: bool = False  # Set to True in standalone unit tests without AWS/LocalStack

    # Database & Cache (Used for readiness checks & downstream worker)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "chirpify_user"
    POSTGRES_PASSWORD: str = "chirpify_secure_pass"
    POSTGRES_DB: str = "chirpify_analytics"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
