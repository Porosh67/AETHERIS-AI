"""
AETHERIS AI Backend — Application Settings
Centralizes all environment variable parsing via pydantic-settings.
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    aetheris_env: str = "development"
    # Serverless (Vercel) note: only /tmp is writable at runtime, and it does
    # not persist across cold starts. Set DATABASE_URL=sqlite:////tmp/aetheris.db
    # as a Vercel env var for deployment; local dev keeps the default file.
    database_url: str = os.environ.get(
        "DATABASE_URL",
        "sqlite:////tmp/aetheris.db" if os.environ.get("VERCEL") else "sqlite:///./aetheris.db",
    )
    max_repair_attempts: int = 3
    inference_timeout_seconds: int = 15

    # watsonx.ai
    watsonx_api_key: str = ""
    watsonx_project_id: str = ""
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    watsonx_model_id: str = "ibm/granite-3-8b-instruct"

    # Evidence signing
    evidence_signing_key: str = "dev-only-signing-key-change-in-prod"

    # CORS
    allowed_origins: str = "http://localhost:5173,http://localhost:3000,https://aetheris-ai-six.vercel.app,https://aetheris-ai-level-infinite.vercel.app"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def watsonx_configured(self) -> bool:
        return bool(self.watsonx_api_key and self.watsonx_project_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()