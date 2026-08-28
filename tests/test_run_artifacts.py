from pathlib import Path

from run_artifacts import create_run_dir, save_mvp_run, serialize_crew_token_usage
from usage_tracker import record_usage, reset_usage_records


class _Usage:
    prompt_tokens = 3
    completion_tokens = 2
    total_tokens = 5


class _CrewResult:
    token_usage = {"total_tokens": 42, "prompt_tokens": 30, "completion_tokens": 12}


def test_create_run_dir(tmp_path: Path):
    run_dir = create_run_dir(base_dir=tmp_path)
    assert run_dir.exists()
    assert run_dir.name.startswith("run-")


def test_save_mvp_run_writes_manifest(tmp_path: Path):
    reset_usage_records()
    record_usage("chat", "gpt-4o-mini", _Usage())
    run_dir = tmp_path / "run-test"
    run_dir.mkdir()

    save_mvp_run(
        run_dir,
        inputs={"started_at": "2026-08-28T00:00:00+00:00", "resume_text_length": 100},
        resume_profile={"status": "ok"},
        jobs=[{"job_title": "Backend"}],
        result={"used_fallback": False},
        crew_usage={"total_tokens": 42},
    )

    manifest = (run_dir / "manifest.json").read_text(encoding="utf-8")
    assert "openai_usage_totals" in manifest
    assert "crew_token_usage" in manifest
    assert (run_dir / "inputs.json").exists()
    assert (run_dir / "result.json").exists()


def test_serialize_crew_token_usage():
    assert serialize_crew_token_usage(_CrewResult()) == _CrewResult.token_usage
    assert serialize_crew_token_usage(object()) == {}
