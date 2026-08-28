"""Persist run inputs/outputs and token usage for offline comparison."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from usage_tracker import usage_snapshot, usage_totals

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path("output")


def create_run_dir(base_dir: Path | None = None) -> Path:
    root = base_dir or DEFAULT_OUTPUT_DIR
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = root / f"run-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def serialize_crew_token_usage(raw_result) -> dict:
    usage = getattr(raw_result, "token_usage", None)
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    return {"raw": str(usage)}


def save_mvp_run(
    run_dir: Path,
    *,
    inputs: dict,
    resume_profile: dict | None,
    jobs: list[dict],
    result: dict,
    crew_usage: dict | None = None,
) -> Path:
    openai_records = usage_snapshot()
    openai_total = usage_totals()
    started_at = inputs.get("started_at")
    finished_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    _write_json(run_dir / "inputs.json", inputs)
    if resume_profile is not None:
        _write_json(run_dir / "resume_profile.json", resume_profile)
    _write_json(run_dir / "jobs.json", {"jobs": jobs})
    _write_json(run_dir / "result.json", result)
    manifest = {
        "started_at": started_at,
        "finished_at": finished_at,
        "openai_usage_records": openai_records,
        "openai_usage_totals": {
            "prompt_tokens": openai_total.prompt_tokens,
            "completion_tokens": openai_total.completion_tokens,
            "total_tokens": openai_total.total_tokens,
            "call_count": openai_total.call_count,
        },
        "crew_token_usage": crew_usage or {},
        "resume_text_length": inputs.get("resume_text_length"),
    }
    _write_json(run_dir / "manifest.json", manifest)

    logger.info(
        "Run artifact saved to %s (openai_tokens=%s, crew_usage=%s)",
        run_dir,
        openai_total.total_tokens,
        bool(crew_usage),
    )
    return run_dir
