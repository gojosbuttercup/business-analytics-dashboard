from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Business Analytics"
    data_path: Path = Path("data/processed/sales.parquet")
    metadata_path: Path = Path("data/processed/metadata.json")
    static_dir: Path = Path("backend/static")
    cache_ttl_seconds: int = 60
    cache_max_entries: int = 64
    model_config = SettingsConfigDict(env_prefix="BA_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

