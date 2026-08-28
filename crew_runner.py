from company_factcheck import build_factcheck
from job_store import upsert_jobs
from main import JobHunterCrew
from models import ChosenJob, JobList, MvpRunResult, RankedJob
from resume_analyze import analyze_resume
from semantic_match import rank_jobs_semantic
from url_verify import apply_url_verification


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
) -> JobList:
    crew_base = JobHunterCrew()
    search_agent = crew_base.job_search_agent()
    extraction = crew_base.job_extraction_task()
    crew = crew_base.crew()
    crew.tasks = [extraction]
    crew.agents = [search_agent]
    result = crew.kickoff(
        inputs={
            "level": level,
            "position": position,
            "location": location,
            "search_queries": search_queries,
        }
    )
    if isinstance(result, JobList):
        return result
    if hasattr(result, "pydantic"):
        return result.pydantic
    return JobList.model_validate(result)


def run_mvp(
    resume_text: str,
    level: str,
    position: str,
    location: str = "Japan",
) -> MvpRunResult:
    profile = analyze_resume(resume_text)
    search_queries = ", ".join(profile.search_queries_ja + profile.search_queries_en)
    job_list = _run_job_search(level, position, location, search_queries)
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

    return MvpRunResult(
        resume_profile=profile if profile.status != "failed" else None,
        ranked_jobs=ranked,
        chosen_job=chosen,
        factcheck=factcheck,
        used_fallback=used_fallback,
        used_raw_resume_fallback=used_raw,
    )
