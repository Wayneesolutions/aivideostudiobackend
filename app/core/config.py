from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Wayne AI Video Studio"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"

    # Security
    SECRET_KEY: str = "dev-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Database — defaults to a local SQLite file so the app runs with zero setup.
    # Swap to a real Postgres URL in .env for production, e.g.:
    # postgresql://user:password@localhost:5432/ai_video_studio
    DATABASE_URL: str = "sqlite:///./app.db"

    # CORS — Vite dev server origins
    FRONTEND_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # AI Services
    OPENAI_API_KEY: str = ""
    FAL_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
