from unittest.mock import patch

from models import Job, RankedJob
from url_verify import apply_url_verification, verify_job_url


@patch("url_verify.httpx.head")
def test_verify_job_url_ok(mock_head):
    mock_head.return_value.status_code = 200
    assert verify_job_url("https://example.com/job") is True


@patch("url_verify.httpx.head")
def test_verify_job_url_fail(mock_head):
    mock_head.return_value.status_code = 404
    assert verify_job_url("https://example.com/missing") is False


def test_apply_url_verification_reorders():
    job_ok = Job(
        job_title="OK",
        company_name="A",
        job_location="Tokyo",
        job_posting_url="https://ok.example/job",
        job_summary="x",
    )
    job_bad = Job(
        job_title="BAD",
        company_name="B",
        job_location="Tokyo",
        job_posting_url="https://bad.example/job",
        job_summary="y",
    )
    ranked = [
        RankedJob(job=job_bad, match_score=5, reason="b", semantic_score=0.9, url_verified=None),
        RankedJob(job=job_ok, match_score=4, reason="a", semantic_score=0.8, url_verified=None),
    ]

    def fake_verify(url, cache=None):
        return "ok.example" in url

    with patch("url_verify.verify_job_url", side_effect=fake_verify):
        result = apply_url_verification(ranked)
    assert result[0].job.job_title == "OK"
    assert result[0].url_verified is True
    assert result[1].url_verified is False
