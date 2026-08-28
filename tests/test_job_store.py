from pathlib import Path

from models import Job
from job_store import count_jobs, list_jobs, upsert_jobs


def _sample_job(url: str, title: str = "Backend") -> Job:
    return Job(
        job_title=title,
        company_name="Co",
        job_location="Tokyo",
        job_posting_url=url,
        job_summary="API development",
    )


def test_upsert_jobs_inserts_new(tmp_path: Path):
    db = tmp_path / "jobs.db"
    result = upsert_jobs([_sample_job("https://example.com/a")], db_path=db)
    assert result.inserted == 1
    assert result.updated == 0
    assert count_jobs(db_path=db) == 1


def test_upsert_jobs_deduplicates_by_url(tmp_path: Path):
    db = tmp_path / "jobs.db"
    upsert_jobs([_sample_job("https://example.com/a", "Backend v1")], db_path=db)
    result = upsert_jobs([_sample_job("https://example.com/a", "Backend v2")], db_path=db)
    assert result.inserted == 0
    assert result.updated == 1
    assert count_jobs(db_path=db) == 1
    stored = list_jobs(db_path=db)
    assert stored[0].job_title == "Backend v2"


def test_upsert_jobs_multiple_urls(tmp_path: Path):
    db = tmp_path / "jobs.db"
    jobs = [
        _sample_job("https://example.com/a"),
        _sample_job("https://example.com/b"),
    ]
    result = upsert_jobs(jobs, db_path=db)
    assert result.inserted == 2
    assert count_jobs(db_path=db) == 2


def test_list_jobs_respects_limit(tmp_path: Path):
    db = tmp_path / "jobs.db"
    upsert_jobs(
        [
            _sample_job("https://example.com/a"),
            _sample_job("https://example.com/b"),
            _sample_job("https://example.com/c"),
        ],
        db_path=db,
    )
    assert len(list_jobs(limit=2, db_path=db)) == 2
