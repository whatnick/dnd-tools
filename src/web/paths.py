from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    # src/web/paths.py -> src/web -> src -> repo
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return repo_root() / "data" / "app"


def db_path() -> Path:
    return data_dir() / "app.db"


def campaigns_dir() -> Path:
    return data_dir() / "campaigns"


def campaign_dir(campaign_id: str) -> Path:
    return campaigns_dir() / campaign_id


def campaign_uploads_dir(campaign_id: str) -> Path:
    return campaign_dir(campaign_id) / "uploads"


def campaign_artifacts_dir(campaign_id: str) -> Path:
    return campaign_dir(campaign_id) / "artifacts"
