from unittest.mock import MagicMock, patch
from pathlib import Path

from models import Job, JobList, RankedJob, ResumeProfile, LanguageSkill
from crew_runner import (
    _profile_search_params,
    _run_job_search,
    run_mvp,
    select_best_job,
)


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


def test_profile_search_params_uses_prefecture():
    profile = ResumeProfile(
        headline_ko="백엔드",
        target_roles=["バックエンドエンジニア"],
        seniority_level="Mid",
        years_of_experience=3.0,
        skills=["Go"],
        languages=[LanguageSkill(code="ja", level="business")],
        visa_status=None,
        preferred_locations=["Tokyo"],
        search_queries_ja=["バックエンド 東京"],
        search_queries_en=[],
        matching_document="summary",
        confidence=0.9,
        parse_warnings=[],
        status="ok",
    )
    level, position, location, queries = _profile_search_params(profile, "東京都")
    assert location == "東京都"
    assert "東京都" in queries
    assert position == "バックエンドエンジニア"


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

    result, crew_usage = _run_job_search("Mid", "Backend", "東京都", "バックエンド 東京")
    assert len(result.jobs) == 1
    assert isinstance(crew_usage, dict)
    mock_crew.kickoff.assert_called_once_with(
        inputs={
            "level": "Mid",
            "position": "Backend",
            "location": "東京都",
            "search_queries": "バックエンド 東京",
        }
    )


@patch("crew_runner.save_mvp_run")
@patch("crew_runner.create_run_dir")
@patch("crew_runner.reset_usage_records")
@patch("crew_runner.apply_url_verification", side_effect=lambda ranked, cache=None: ranked)
@patch("crew_runner.upsert_jobs")
@patch("crew_runner.rank_jobs_semantic")
@patch("crew_runner._run_job_search")
@patch("crew_runner.analyze_resume")
def test_run_mvp_orchestrates_r_e(
    mock_analyze,
    mock_search,
    mock_rank,
    mock_upsert,
    _mock_url,
    _mock_reset_usage,
    mock_create_run_dir,
    mock_save_run,
):
    profile = ResumeProfile(
        headline_ko="백엔드",
        target_roles=["バックエンドエンジニア"],
        seniority_level="Mid",
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
        job_location="東京都",
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

    result = run_mvp("resume text", "東京都")

    mock_analyze.assert_called_once_with("resume text")
    mock_search.assert_called_once()
    search_args = mock_search.call_args[0]
    assert search_args[2] == "東京都"
    mock_rank.assert_called_once_with("resume text", [job], profile)
    mock_upsert.assert_called_once_with([job])
    mock_save_run.assert_called_once()
    assert result.run_artifact_dir == "output/run-test"
    assert result.resume_profile == profile


def test_run_mvp_legacy_four_arg_call():
    """Old Streamlit call style: run_mvp(text, level, position, location)."""
    with (
        patch("crew_runner.reset_usage_records"),
        patch("crew_runner.create_run_dir", return_value=Path("output/run-test")),
        patch("crew_runner.analyze_resume") as mock_analyze,
        patch("crew_runner._run_job_search") as mock_search,
        patch("crew_runner.upsert_jobs"),
        patch("crew_runner.rank_jobs_semantic") as mock_rank,
        patch("crew_runner.apply_url_verification", side_effect=lambda r, cache=None: r),
        patch("crew_runner.save_mvp_run"),
    ):
        profile = ResumeProfile(
            headline_ko="x",
            target_roles=["Engineer"],
            seniority_level="Mid",
            years_of_experience=3.0,
            skills=["Go"],
            languages=[LanguageSkill(code="ja", level="business")],
            visa_status=None,
            preferred_locations=["Tokyo"],
            search_queries_ja=["エンジニア"],
            search_queries_en=[],
            matching_document="x",
            confidence=0.9,
            parse_warnings=[],
            status="ok",
        )
        mock_analyze.return_value = profile
        job = Job(
            job_title="Backend",
            company_name="Co",
            job_location="東京都",
            job_posting_url="https://example.com",
            job_summary="API",
        )
        mock_search.return_value = (JobList(jobs=[job]), {})
        mock_rank.return_value = (
            [RankedJob(job=job, match_score=4, reason="ok", semantic_score=0.7)],
            False,
            False,
        )
        run_mvp("resume", "Senior", "Backend", "大阪府")

        assert mock_search.call_args[0][2] == "大阪府"


def test_run_mvp_requires_prefecture():
    import pytest

    with pytest.raises(ValueError, match="도도부현"):
        run_mvp("resume", "")
