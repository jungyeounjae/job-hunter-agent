from unittest.mock import MagicMock, patch
from pathlib import Path

from models import Job, JobList, RankedJob
from crew_runner import _run_job_search, run_mvp, select_best_job


def test_select_best_job_prefers_verified_and_semantic():
    jobs = [
        RankedJob(
            job=Job(
                job_title="High",
                company_name="B",
                job_location="Tokyo",
                job_posting_url="https://b.example",
                job_summary="y",
            ),
            match_score=5,
            reason="b",
            semantic_score=0.9,
            url_verified=True,
        ),
        RankedJob(
            job=Job(
                job_title="Low",
                company_name="A",
                job_location="Tokyo",
                job_posting_url="https://a.example",
                job_summary="x",
            ),
            match_score=3,
            reason="a",
            semantic_score=0.5,
            url_verified=False,
        ),
    ]
    chosen = select_best_job(jobs)
    assert chosen.job.job_title == "High"


@patch("crew_runner.JobHunterCrew")
def test_run_job_search_passes_search_queries(mock_crew_cls):
    mock_crew = MagicMock()
    mock_crew_cls.return_value = mock_crew
    mock_crew.job_search_agent.return_value = MagicMock()
    mock_crew.job_extraction_task.return_value = MagicMock()
    mock_crew.crew.return_value = mock_crew

    job = Job(
        job_title="Backend",
        company_name="Co",
        job_location="Tokyo",
        job_posting_url="https://example.com",
        job_summary="API",
    )
    mock_crew.kickoff.return_value = JobList(jobs=[job])

    result, crew_usage = _run_job_search("Senior", "Backend", "Japan", "フルスタック 東京, full stack")
    assert len(result.jobs) == 1
    assert isinstance(crew_usage, dict)
    mock_crew.kickoff.assert_called_once_with(
        inputs={
            "level": "Senior",
            "position": "Backend",
            "location": "Japan",
            "search_queries": "フルスタック 東京, full stack",
        }
    )


@patch("crew_runner.save_mvp_run")
@patch("crew_runner.create_run_dir")
@patch("crew_runner.reset_usage_records")
@patch("crew_runner.build_factcheck")
@patch("crew_runner.apply_url_verification", side_effect=lambda ranked, cache=None: ranked)
@patch("crew_runner.upsert_jobs")
@patch("crew_runner.rank_jobs_semantic")
@patch("crew_runner._run_job_search")
@patch("crew_runner.analyze_resume")
def test_run_mvp_orchestrates_r_e_c(
    mock_analyze,
    mock_search,
    mock_rank,
    mock_upsert,
    _mock_url,
    mock_factcheck,
    _mock_reset_usage,
    mock_create_run_dir,
    mock_save_run,
):
    from models import ChosenJob, CompanyFactcheck, ResumeProfile, LanguageSkill

    profile = ResumeProfile(
        headline_ko="백엔드",
        target_roles=["백엔드 엔지니어"],
        seniority_level="Senior",
        years_of_experience=5.0,
        skills=["Python"],
        languages=[LanguageSkill(code="ko", level="native")],
        visa_status=None,
        preferred_locations=["Tokyo"],
        search_queries_ja=["バックエンド 東京"],
        search_queries_en=["backend Tokyo"],
        matching_document="백엔드 5년",
        confidence=0.9,
        parse_warnings=[],
        status="ok",
    )
    mock_analyze.return_value = profile

    job = Job(
        job_title="Backend",
        company_name="Co",
        job_location="Tokyo",
        job_posting_url="https://example.com",
        job_summary="API",
    )
    mock_create_run_dir.return_value = Path("output/run-test")
    mock_search.return_value = (JobList(jobs=[job]), {"total_tokens": 10})

    ranked_job = RankedJob(
        job=job,
        match_score=4,
        reason="good",
        semantic_score=0.7,
        url_verified=True,
    )
    mock_rank.return_value = ([ranked_job], False, False)

    mock_factcheck.return_value = CompanyFactcheck(
        corporate_number=None,
        gbiz_fields={},
        risk_tags=[],
        summary_ko="ok",
        sources=[],
        status="public_unconfirmed",
    )

    result = run_mvp("resume text", "Senior", "Backend", "Japan")

    mock_analyze.assert_called_once_with("resume text")
    mock_search.assert_called_once_with(
        "Senior", "Backend", "Japan", "バックエンド 東京, backend Tokyo"
    )
    mock_rank.assert_called_once_with("resume text", [job], profile)
    mock_upsert.assert_called_once_with([job])
    mock_save_run.assert_called_once()
    assert result.run_artifact_dir == "output/run-test"
    assert result.resume_profile == profile
    assert result.used_raw_resume_fallback is False
