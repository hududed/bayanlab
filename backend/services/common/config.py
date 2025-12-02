"""
Configuration management for BayanLab Community Data Backbone
"""
import os
import yaml
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""
    # Database - MUST be set via environment or .env, no defaults
    database_url: str
    database_url_sync: str

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1

    # Geocoding
    geocoder_provider: str = "nominatim"
    geocoder_user_agent: str = "BayanLab/1.0"
    geocoder_rate_limit: float = 1.0  # seconds between requests

    # Placekey
    placekey_api_key: str | None = None

    # Google Calendar API
    google_application_credentials: str | None = None

    # Google Places API (for business enrichment)
    google_places_api_key: str | None = None
    google_custom_search_api_key: str | None = None
    google_custom_search_engine_id: str | None = None
    google_geocoding_api_key: str | None = None

    # Neon database (production)
    neon_db_url: str | None = None

    # SendGrid Email
    sendgrid_api_key: str | None = None
    sendgrid_from_email: str = "info@prowasl.com"
    sendgrid_from_name: str = "ProWasl"
    sendgrid_reply_to: str = "info@prowasl.com"
    admin_email: str | None = None  # Email for admin notifications (claim submissions, etc.)

    # Internal Validation Tool API Keys
    internal_api_key: str | None = None  # For team access to validation tool
    admin_api_key: str | None = None  # For admin-only approval operations

    # Region (default for V1)
    default_region: str = "CO"

    # Paths (relative to backend/services/common/config.py)
    config_dir: Path = Path(__file__).parent.parent.parent / "configs"
    sql_dir: Path = Path(__file__).parent.parent.parent / "sql"
    seed_dir: Path = Path(__file__).parent.parent.parent.parent / "seed"  # At repo root
    exports_dir: Path = Path(__file__).parent.parent.parent.parent / "exports"  # At repo root

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = Path(__file__).parent.parent.parent.parent / ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


@lru_cache()
def load_yaml_config(filename: str) -> dict:
    """Load YAML configuration file"""
    settings = get_settings()
    config_path = settings.config_dir / filename

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_regions_config() -> dict:
    """Get regions configuration"""
    return load_yaml_config("regions.yaml")


def get_sources_config() -> dict:
    """Get sources configuration"""
    return load_yaml_config("sources.yaml")


def get_dq_rules_config() -> dict:
    """Get data quality rules configuration"""
    return load_yaml_config("dq_rules.yaml")


def get_region_bbox(region: str) -> dict:
    """Get bounding box for a region"""
    regions = get_regions_config()
    if region not in regions.get("regions", {}):
        raise ValueError(f"Unknown region: {region}")

    return regions["regions"][region]["bbox"]


def get_region_timezone(region: str) -> str:
    """Get timezone for a region"""
    regions = get_regions_config()
    if region not in regions.get("regions", {}):
        raise ValueError(f"Unknown region: {region}")

    return regions["regions"][region]["timezone"]
