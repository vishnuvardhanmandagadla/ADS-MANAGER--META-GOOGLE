"""Load and expose all configuration: env vars + YAML files + client configs."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Paths
ROOT = Path(__file__).resolve().parents[3]  # project/backend/
CONFIG_DIR = ROOT / "config"
CLIENTS_DIR = CONFIG_DIR / "clients"


# ── Environment / secrets ──────────────────────────────────────────────────────


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "development"
    secret_key: str = "change-me"
    debug: bool = True

    # Database
    database_url: str = f"sqlite+aiosqlite:///{ROOT}/ads_engine.db"

    # Claude AI
    anthropic_api_key: Optional[str] = None

    # Meta
    meta_app_id: Optional[str] = None
    meta_app_secret: Optional[str] = None
    meta_access_token: Optional[str] = None

    # Google Ads
    google_ads_developer_token: Optional[str] = None
    google_ads_client_id: Optional[str] = None
    google_ads_client_secret: Optional[str] = None
    google_ads_refresh_token: Optional[str] = None

    # Notifications
    whatsapp_api_token: Optional[str] = None
    whatsapp_phone_number_id: Optional[str] = None
    telegram_bot_token: Optional[str] = None

    # Admin
    admin_email: str = "admin@example.com"
    admin_whatsapp: Optional[str] = None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


# ── YAML loaders ───────────────────────────────────────────────────────────────


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_app_config() -> dict:
    path = CONFIG_DIR / "settings.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


@lru_cache
def get_safety_config() -> dict:
    path = CONFIG_DIR / "safety.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def get_client_config(client_id: str) -> dict:
    """Load a single client's YAML config."""
    path = CLIENTS_DIR / f"{client_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No config found for client '{client_id}'")
    with open(path) as f:
        return yaml.safe_load(f)


def list_clients() -> list[str]:
    """Return all configured client IDs."""
    return [p.stem for p in CLIENTS_DIR.glob("*.yaml")]
