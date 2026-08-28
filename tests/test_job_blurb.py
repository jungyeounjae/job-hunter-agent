from unittest.mock import patch

from models import Job
from job_blurb import build_job_blurbs


@patch("job_blurb.generate_korean_text", return_value="백엔드 API 개발 포지션")
def test_build_job_blurbs_caches_by_url(mock_gen):
    job = Job(
        job_title="Backend",
        company_name="Co",
        job_location="Tokyo",
        job_posting_url="https://example.com/job/1",
        job_summary="API development",
    )
    cache: dict[str, str] = {}
    blurbs = build_job_blurbs([job, job], cache=cache)
    assert blurbs["https://example.com/job/1"] == "백엔드 API 개발 포지션"
    mock_gen.assert_called_once()
    assert cache["https://example.com/job/1"] == "백엔드 API 개발 포지션"
