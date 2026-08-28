"""SQLite job corpus — dedupe by job_posting_url."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from models import Job

DEFAULT_DB_PATH = Path("data/jobs.db")


@dataclass
class UpsertResult:
    inserted: int
    updated: int

    @property
    def total(self) -> int:
        return self.inserted + self.updated


def get_db_path() -> Path:
    raw = os.environ.get("JOB_DB_PATH")
    return Path(raw) if raw else DEFAULT_DB_PATH


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | None = None) -> Path:
    path = db_path or get_db_path()
    with _connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_posting_url TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    return path


def upsert_jobs(jobs: list[Job], db_path: Path | None = None) -> UpsertResult:
    if not jobs:
        return UpsertResult(inserted=0, updated=0)

    path = init_db(db_path)
    inserted = 0
    updated = 0
    now = _utc_now()

    with _connect(path) as conn:
        for job in jobs:
            payload = job.model_dump_json()
            url = job.job_posting_url
            existing = conn.execute(
                "SELECT job_posting_url FROM jobs WHERE job_posting_url = ?",
                (url,),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE jobs
                    SET payload_json = ?, last_seen_at = ?
                    WHERE job_posting_url = ?
                    """,
                    (payload, now, url),
                )
                updated += 1
            else:
                conn.execute(
                    """
                    INSERT INTO jobs (job_posting_url, payload_json, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (url, payload, now, now),
                )
                inserted += 1
        conn.commit()

    return UpsertResult(inserted=inserted, updated=updated)


def list_jobs(limit: int | None = None, db_path: Path | None = None) -> list[Job]:
    path = init_db(db_path)
    query = "SELECT payload_json FROM jobs ORDER BY last_seen_at DESC"
    params: tuple = ()
    if limit is not None:
        query += " LIMIT ?"
        params = (limit,)

    with _connect(path) as conn:
        rows = conn.execute(query, params).fetchall()

    return [Job.model_validate_json(row["payload_json"]) for row in rows]


def count_jobs(db_path: Path | None = None) -> int:
    path = init_db(db_path)
    with _connect(path) as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()
    return int(row["n"])
