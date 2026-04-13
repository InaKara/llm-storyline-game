from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    evaluator_model: str = "gpt-4o"
    responder_model: str = "gpt-4o-mini"
    scenario_root_path: Path = Path("scenarios")
    trace_output_path: Path = Path("traces")
    asset_base_url: str = "/assets"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    return Settings()
