from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .paths import db_path, data_dir


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect() -> sqlite3.Connection:
    data_dir().mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS campaign (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS artifact (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                text_content TEXT,
                file_path TEXT,
                meta_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (campaign_id) REFERENCES campaign(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS job (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                result_artifact_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (campaign_id) REFERENCES campaign(id) ON DELETE CASCADE,
                FOREIGN KEY (result_artifact_id) REFERENCES artifact(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_artifact_campaign_created_at
                ON artifact (campaign_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_job_campaign_updated_at
                ON job (campaign_id, updated_at DESC);
            """
        )


@dataclass(frozen=True)
class Campaign:
    id: str
    name: str
    created_at: str


@dataclass(frozen=True)
class Artifact:
    id: str
    campaign_id: str
    kind: str
    title: str
    text_content: str | None
    file_path: str | None
    meta: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class Job:
    id: str
    campaign_id: str
    kind: str
    status: str
    message: str | None
    result_artifact_id: str | None
    created_at: str
    updated_at: str


def create_campaign(name: str) -> Campaign:
    campaign_id = uuid.uuid4().hex
    created_at = _utcnow_iso()

    with connect() as conn:
        conn.execute(
            "INSERT INTO campaign (id, name, created_at) VALUES (?, ?, ?)",
            (campaign_id, name, created_at),
        )

    return Campaign(id=campaign_id, name=name, created_at=created_at)


def list_campaigns() -> list[Campaign]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, name, created_at FROM campaign ORDER BY created_at DESC"
        ).fetchall()

    return [Campaign(id=r["id"], name=r["name"], created_at=r["created_at"]) for r in rows]


def get_campaign(campaign_id: str) -> Campaign | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, name, created_at FROM campaign WHERE id = ?",
            (campaign_id,),
        ).fetchone()

    if row is None:
        return None

    return Campaign(id=row["id"], name=row["name"], created_at=row["created_at"])


def create_artifact(
    *,
    campaign_id: str,
    kind: str,
    title: str,
    text_content: str | None = None,
    file_path: str | None = None,
    meta: dict[str, Any] | None = None,
) -> Artifact:
    artifact_id = uuid.uuid4().hex
    created_at = _utcnow_iso()
    meta_json = json.dumps(meta or {}, ensure_ascii=False)

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO artifact (
                id, campaign_id, kind, title, text_content, file_path, meta_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (artifact_id, campaign_id, kind, title, text_content, file_path, meta_json, created_at),
        )

    return Artifact(
        id=artifact_id,
        campaign_id=campaign_id,
        kind=kind,
        title=title,
        text_content=text_content,
        file_path=file_path,
        meta=json.loads(meta_json),
        created_at=created_at,
    )


def list_artifacts(campaign_id: str) -> list[Artifact]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, campaign_id, kind, title, text_content, file_path, meta_json, created_at
            FROM artifact
            WHERE campaign_id = ?
            ORDER BY created_at DESC
            """,
            (campaign_id,),
        ).fetchall()

    artifacts: list[Artifact] = []
    for r in rows:
        artifacts.append(
            Artifact(
                id=r["id"],
                campaign_id=r["campaign_id"],
                kind=r["kind"],
                title=r["title"],
                text_content=r["text_content"],
                file_path=r["file_path"],
                meta=json.loads(r["meta_json"] or "{}"),
                created_at=r["created_at"],
            )
        )
    return artifacts


def get_artifact(artifact_id: str) -> Artifact | None:
    with connect() as conn:
        r = conn.execute(
            """
            SELECT id, campaign_id, kind, title, text_content, file_path, meta_json, created_at
            FROM artifact
            WHERE id = ?
            """,
            (artifact_id,),
        ).fetchone()

    if r is None:
        return None

    return Artifact(
        id=r["id"],
        campaign_id=r["campaign_id"],
        kind=r["kind"],
        title=r["title"],
        text_content=r["text_content"],
        file_path=r["file_path"],
        meta=json.loads(r["meta_json"] or "{}"),
        created_at=r["created_at"],
    )


def create_job(*, campaign_id: str, kind: str, status: str, message: str | None = None) -> Job:
    job_id = uuid.uuid4().hex
    now = _utcnow_iso()

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO job (id, campaign_id, kind, status, message, result_artifact_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (job_id, campaign_id, kind, status, message, now, now),
        )

    return Job(
        id=job_id,
        campaign_id=campaign_id,
        kind=kind,
        status=status,
        message=message,
        result_artifact_id=None,
        created_at=now,
        updated_at=now,
    )


def update_job(
    *,
    job_id: str,
    status: str,
    message: str | None = None,
    result_artifact_id: str | None = None,
) -> None:
    now = _utcnow_iso()
    with connect() as conn:
        conn.execute(
            """
            UPDATE job
            SET status = ?, message = ?, result_artifact_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, message, result_artifact_id, now, job_id),
        )


def list_jobs(campaign_id: str, limit: int = 10) -> list[Job]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, campaign_id, kind, status, message, result_artifact_id, created_at, updated_at
            FROM job
            WHERE campaign_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (campaign_id, limit),
        ).fetchall()

    return [
        Job(
            id=r["id"],
            campaign_id=r["campaign_id"],
            kind=r["kind"],
            status=r["status"],
            message=r["message"],
            result_artifact_id=r["result_artifact_id"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]


def get_job(job_id: str) -> Job | None:
    with connect() as conn:
        r = conn.execute(
            """
            SELECT id, campaign_id, kind, status, message, result_artifact_id, created_at, updated_at
            FROM job
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

    if r is None:
        return None

    return Job(
        id=r["id"],
        campaign_id=r["campaign_id"],
        kind=r["kind"],
        status=r["status"],
        message=r["message"],
        result_artifact_id=r["result_artifact_id"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )
