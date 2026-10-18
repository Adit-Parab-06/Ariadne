from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[str(ROOT_ENV), ".env"],
        env_file_encoding="utf-8",
        extra="ignore"
    )

    FALKORDB_HOST: str = "localhost"
    FALKORDB_PORT: int = 6379
    FALKORDB_USERNAME: Optional[str] = None
    FALKORDB_PASSWORD: Optional[str] = None
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_EMBED_MODEL: str = "gemini-embedding-001"
    EMBED_DIM: int = 768
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,http://localhost:4173,http://127.0.0.1:4173"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
