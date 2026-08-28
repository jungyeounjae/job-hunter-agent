from ai_provider import AiProviderError, generate_korean_text
from models import Job


def _job_source_text(job: Job) -> str:
    parts = [job.job_title, job.company_name, job.job_summary]
    if job.full_raw_job_description:
        parts.append(job.full_raw_job_description)
    return "\n".join(p for p in parts if p)[:3000]


def build_job_blurbs(
    jobs: list[Job],
    cache: dict[str, str] | None = None,
) -> dict[str, str]:
    blurbs: dict[str, str] = {}
    seen: set[str] = set()
    for job in jobs:
        url = job.job_posting_url
        if url in seen:
            continue
        seen.add(url)
        if cache is not None and url in cache:
            blurbs[url] = cache[url]
            continue
        prompt = (
            "다음 일본 채용공고를 한국어로 1–2문장 요약하세요. 직무와 요구 스킬만.\n\n"
            f"{_job_source_text(job)}"
        )
        try:
            blurb = generate_korean_text(prompt)
            blurbs[url] = blurb
            if cache is not None:
                cache[url] = blurb
        except AiProviderError:
            continue
    return blurbs
