from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://cookai:cookai@localhost:5432/cookai"
    database_url_sync: str = "postgresql://cookai:cookai@localhost:5432/cookai"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30

    # Anthropic
    anthropic_api_key: str = ""

    # OpenAI (Whisper)
    openai_api_key: str = ""

    # CORS
    cors_origins: str = "http://localhost:8081,http://localhost:19006"

    # Video processing
    max_video_duration_seconds: int = 300
    temp_media_dir: str = "./tmp/media"


settings = Settings()
