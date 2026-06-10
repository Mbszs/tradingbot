"""Application settings (pydantic-settings, env-prefix SERPENT_)."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Override via environment, e.g. SERPENT_DB_PATH."""

    model_config = SettingsConfigDict(env_prefix="SERPENT_", env_file=".env", extra="ignore")

    db_path: Path = Path("data/serpent.db")
    parquet_dir: Path = Path("data/parquet")
    signals_dir: Path = Path("data/signals")
    firms_dir: Path | None = None  # defaults to core/survival/firms

    mc_paths: int = 20_000
    mc_seed: int = 42
    mc_block_size: int = 5


def get_settings() -> Settings:
    """Build a fresh Settings instance (no global state)."""
    return Settings()
