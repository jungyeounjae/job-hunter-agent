from collections.abc import Callable

from job_store import upsert_jobs
from main import JobHunterCrew
from models import ChosenJob, JobList, MvpRunResult, RankedJob, ResumeProfile
from resume_analyze import analyze_resume
from run_artifacts import create_run_dir, save_mvp_run, serialize_crew_token_usage
from semantic_match import rank_jobs_semantic
from url_verify import apply_url_verification
from usage_tracker import reset_usage_records

ProgressCallback = Callable[[str], None]


def select_best_job(ranked_jobs: list[RankedJob]) -> ChosenJob:
    if not ranked_jobs:
        raise ValueError("매칭된 공고가 없습니다.")
    best = ranked_jobs[0]
    return ChosenJob(job=best.job, selected=True, reason=best.reason)


def _profile_search_params(profile: ResumeProfile, prefecture: str) -> tuple[str, str, str, str]:
    level = profile.seniority_level or "Mid"
    position = profile.target_roles[0] if profile.target_roles else "Engineer"
    location = prefecture.strip()
    queries = [*profile.search_queries_ja, *profile.search_queries_en]
    if location and location not in ", ".join(queries):
        queries.append(location)
    search_queries = ", ".join(q.strip() for q in queries if q and q.strip())
    return level, position, location, search_queries


def _run_job_search(
    level: str,
    position: str,
    location: str,
    search_queries: str = "",
) -> tuple[JobList, dict]:
    crew_base = JobHunterCrew()
    search_agent = crew_base.job_search_agent()
    extraction = crew_base.job_extraction_task()
    crew = crew_base.crew()
    crew.tasks = [extraction]
    crew.agents = [search_agent]
    crew.verbose = False
    raw = crew.kickoff(
        inputs={
            "level": level,
            "position": position,
            "location": location,
            "search_queries": search_queries,
        }
    )
    crew_usage = serialize_crew_token_usage(raw)
    if isinstance(raw, JobList):
        return raw, crew_usage
    if hasattr(raw, "pydantic"):
        return raw.pydantic, crew_usage
    return JobList.model_validate(raw), crew_usage


def _notify(on_progress: ProgressCallback | None, message: str) -> None:
    if on_progress is not None:
        on_progress(message)


def run_mvp(
    resume_text: str,
    prefecture: str,
    position: str | None = None,
    location: str | None = None,
    *,
    on_progress: ProgressCallback | None = None,
) -> MvpRunResult:
    """Run R→E pipeline.

    Preferred: ``run_mvp(resume_text, prefecture)`` e.g. ``("...", "東京都")``.
    Legacy (deprecated): ``run_mvp(resume_text, level, position, location)`` —
    ``location`` is used as prefecture; level/position come from ResumeProfile.
    """
    from datetime import datetime, timezone

    if position is not None:
        prefecture = (location or prefecture or "").strip()
    else:
        prefecture = prefecture.strip()

    if not prefecture:
        raise ValueError("근무 희망 도도부현을 선택해 주세요.")

    reset_usage_records()
    run_dir = create_run_dir()
    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    _notify(on_progress, "이력서 분석 중…")
    profile = analyze_resume(resume_text)
    level, position, location, search_queries = _profile_search_params(profile, prefecture)

    _notify(on_progress, "일본 공고 검색 중…")
    job_list, crew_usage = _run_job_search(level, position, location, search_queries)
    if not job_list.jobs:
        raise ValueError("조건에 맞는 공고를 찾지 못했습니다. 다른 도도부현을 선택해 보세요.")

    upsert_jobs(job_list.jobs)

    _notify(on_progress, "의미 매칭 중…")
    ranked, used_fallback, used_raw = rank_jobs_semantic(
        resume_text, job_list.jobs, profile
    )

    _notify(on_progress, "공고 URL 확인 중…")
    url_cache: dict[str, bool] = {}
    ranked = apply_url_verification(ranked, cache=url_cache)
    chosen = select_best_job(ranked)

    _notify(on_progress, "완료")

    result = MvpRunResult(
        resume_profile=profile if profile.status != "failed" else None,
        ranked_jobs=ranked,
        chosen_job=chosen,
        used_fallback=used_fallback,
        used_raw_resume_fallback=used_raw,
    )

    save_mvp_run(
        run_dir,
        inputs={
            "started_at": started_at,
            "prefecture": prefecture,
            "derived_level": level,
            "derived_position": position,
            "location": location,
            "search_queries": search_queries,
            "resume_text": resume_text,
            "resume_text_length": len(resume_text),
        },
        resume_profile=profile.model_dump() if profile.status != "failed" else None,
        jobs=[job.model_dump(mode="json") for job in job_list.jobs],
        result=result.model_dump(mode="json"),
        crew_usage=crew_usage,
    )
    result.run_artifact_dir = str(run_dir)
    return result
