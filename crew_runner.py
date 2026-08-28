from company_factcheck import build_factcheck
from job_store import upsert_jobs
from main import JobHunterCrew
from models import ChosenJob, JobList, MvpRunResult, RankedJob
from resume_analyze import analyze_resume
from run_artifacts import create_run_dir, save_mvp_run, serialize_crew_token_usage
from semantic_match import rank_jobs_semantic
from url_verify import apply_url_verification
from usage_tracker import reset_usage_records


def select_best_job(ranked_jobs: list[RankedJob]) -> ChosenJob:
    if not ranked_jobs:
        raise ValueError("매칭된 공고가 없습니다.")
    best = ranked_jobs[0]
    return ChosenJob(job=best.job, selected=True, reason=best.reason)


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


def run_mvp(
    resume_text: str,
    level: str,
    position: str,
    location: str = "Japan",
) -> MvpRunResult:
    from datetime import datetime, timezone

    reset_usage_records()
    run_dir = create_run_dir()
    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    profile = analyze_resume(resume_text)
    search_queries = ", ".join(profile.search_queries_ja + profile.search_queries_en)
    job_list, crew_usage = _run_job_search(level, position, location, search_queries)
    if not job_list.jobs:
        raise ValueError("조건에 맞는 공고를 찾지 못했습니다. 검색 조건을 완화해 보세요.")

    upsert_jobs(job_list.jobs)

    ranked, used_fallback, used_raw = rank_jobs_semantic(
        resume_text, job_list.jobs, profile
    )
    url_cache: dict[str, bool] = {}
    ranked = apply_url_verification(ranked, cache=url_cache)
    chosen = select_best_job(ranked)
    factcheck = build_factcheck(chosen.job.company_name, chosen.job.job_posting_url)

    result = MvpRunResult(
        resume_profile=profile if profile.status != "failed" else None,
        ranked_jobs=ranked,
        chosen_job=chosen,
        factcheck=factcheck,
        used_fallback=used_fallback,
        used_raw_resume_fallback=used_raw,
    )

    save_mvp_run(
        run_dir,
        inputs={
            "started_at": started_at,
            "level": level,
            "position": position,
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
