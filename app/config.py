"""Application configuration from environment."""

from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.environ.get("HT_SECRET_KEY", "dev-change-me-for-production")
    DATA_DIR = Path(os.environ.get("HT_DATA_DIR", ROOT_DIR / "data")).resolve()
    DATABASE_PATH = DATA_DIR / "health.db"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "HT_DATABASE_URL",
        f"sqlite:///{DATABASE_PATH}",
    )
    SQLALCHEMY_ECHO = _bool(os.environ.get("HT_SQL_ECHO"), False)

    HOST = os.environ.get("HT_HOST", "127.0.0.1")
    PORT = int(os.environ.get("HT_PORT", "8088"))
    DEBUG = _bool(os.environ.get("HT_DEBUG"), False)
    TIMEZONE = os.environ.get("HT_TIMEZONE", "America/New_York")

    @classmethod
    def ensure_directories(cls) -> None:
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
