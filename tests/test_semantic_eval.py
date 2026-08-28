import json
from pathlib import Path

import pytest

from models import Job, LabeledJob, ResumeProfile
from semantic_eval import (
    DEFAULT_EVAL_DIR,
    compute_metrics,
    load_labeled_jobs,
    load_resume_profile,
    load_resume_text,
    run_eval,
)


def test_eval_fixture_has_eighteen_jobs():
    labeled = load_labeled_jobs()
    assert len(labeled) == 18
    match = [x for x in labeled if x.label == "match"]
    no_match = [x for x in labeled if x.label == "no_match"]
    assert len(match) == 9
    assert len(no_match) == 9


def test_eval_fixture_resume_and_profile_load():
    text = load_resume_text()
    assert "PHP" in text
    profile = load_resume_profile()
    assert profile.status == "ok"
    assert "Go" in profile.skills


def test_compute_metrics_separation():
    ranked = [
        ("m01", "match", 0.8),
        ("m02", "match", 0.7),
        ("n01", "no_match", 0.3),
        ("n02", "no_match", 0.2),
    ]
    metrics = compute_metrics(ranked)
    assert metrics.score_separation > 0
    assert metrics.precision_at_5 == 0.5


def test_compute_metrics_precision_at_k():
    ranked = [
        ("m01", "match", 0.9),
        ("m02", "match", 0.8),
        ("m03", "match", 0.7),
        ("n01", "no_match", 0.1),
    ]
    metrics = compute_metrics(ranked)
    assert metrics.precision_at_5 == 0.75


def test_labeled_job_schema():
    item = LabeledJob(
        id="m01",
        label="match",
        rationale_ko="test",
        job=Job(
            job_title="Backend",
            company_name="Co",
            job_location="Tokyo",
            job_posting_url="https://example.com/eval/m01",
            job_summary="API",
        ),
    )
    assert item.label == "match"


@pytest.mark.live
def test_run_eval_live_openai():
    """Requires real OPENAI_API_KEY. Run: uv run pytest -m live tests/test_semantic_eval.py -v"""
    import os

    key = os.environ.get("OPENAI_API_KEY", "")
    if not key or key == "test-key":
        pytest.skip("Real OPENAI_API_KEY required for live eval")

    metrics, _ranked = run_eval()
    assert metrics.job_count == 18
    assert metrics.match_count == 9
    assert metrics.no_match_count == 9
    assert metrics.score_separation > 0
