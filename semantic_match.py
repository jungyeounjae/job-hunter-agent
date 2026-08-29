import math
from collections.abc import Callable

from ai_provider import AiProviderError, embed_texts, generate_korean_text
from job_blurb import build_job_blurbs
from models import Job, RankedJob, ResumeProfile

# LLM cost control: blurbs/reasons only for top-ranked jobs after embedding sort.
BLURB_TOP_K = 8
REASON_TOP_K = 5


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_job_document(job: Job, blurb_ko: str | None = None) -> str:
    parts = [
        job.job_title,
        job.company_name,
        job.job_location,
        job.job_summary,
    ]
    if job.full_raw_job_description:
        parts.append(job.full_raw_job_description)
    if job.required_technologies:
        parts.append(", ".join(job.required_technologies))
    if job.overseas_applicable is not None:
        parts.append(f"overseas_applicable: {job.overseas_applicable}")
    if job.visa_support is not None:
        parts.append(f"visa_support: {job.visa_support}")
    if job.japanese_level:
        parts.append(f"japanese_level: {job.japanese_level}")
    if job.foreign_hire_track_record is not None:
        parts.append(f"foreign_hire_track_record: {job.foreign_hire_track_record}")
    doc = "\n".join(p for p in parts if p)
    if blurb_ko:
        return f"[한국어 요약] {blurb_ko}\n{doc}"
    return doc


def _fallback_rank(jobs: list[Job]) -> list[RankedJob]:
    return [
        RankedJob(
            job=job,
            match_score=3,
            reason="OpenAI 장애로 키워드 기반 임시 순위입니다.",
            semantic_score=None,
            url_verified=None,
        )
        for job in jobs
    ]


def _build_reason_prompt(
    score: float,
    candidate_doc: str,
    job_doc: str,
    profile: ResumeProfile | None,
) -> str:
    profile_hint = ""
    if profile and profile.status != "failed":
        profile_hint = (
            f"\n[프로필 요약] {profile.headline_ko}\n"
            f"[핵심 스킬] {', '.join(profile.skills[:10])}"
        )
    return (
        "당신은 한국→일본 취업 코치입니다. 아래 이력서와 일본 채용공고의 "
        f"의미적 유사도는 {score:.2f}입니다. 한국어로 2문장 이내 매칭 이유를 작성하세요.\n\n"
        f"[이력서]{profile_hint}\n{candidate_doc[:2000]}\n\n[공고]\n{job_doc[:2000]}"
    )


def _score_only_reason(score: float) -> str:
    return f"의미 유사도 {score:.2f}"


def rank_jobs_semantic(
    resume_text: str,
    jobs: list[Job],
    profile: ResumeProfile | None = None,
    *,
    reason_top_k: int = REASON_TOP_K,
    blurb_top_k: int = BLURB_TOP_K,
) -> tuple[list[RankedJob], bool, bool]:
    if not jobs:
        return [], False, False

    use_profile = bool(
        profile is not None
        and profile.status != "failed"
        and profile.matching_document.strip()
    )
    candidate_doc = profile.matching_document if use_profile else resume_text
    used_raw_resume_fallback = not use_profile

    documents = [build_job_document(job) for job in jobs]
    try:
        vectors = embed_texts([candidate_doc, *documents])
    except AiProviderError:
        return _fallback_rank(jobs), True, used_raw_resume_fallback

    resume_vec = vectors[0]
    scored: list[tuple[float, Job, str]] = []
    for job, job_vec, doc in zip(jobs, vectors[1:], documents):
        score = cosine_similarity(resume_vec, job_vec)
        scored.append((score, job, doc))
    scored.sort(key=lambda item: item[0], reverse=True)

    blurbs = build_job_blurbs([job for _, job, _ in scored[:blurb_top_k]])

    ranked: list[RankedJob] = []
    for rank_idx, (score, job, doc) in enumerate(scored):
        blurb = blurbs.get(job.job_posting_url)
        doc_with_blurb = build_job_document(job, blurb) if blurb else doc
        if rank_idx < reason_top_k:
            prompt = _build_reason_prompt(score, candidate_doc, doc_with_blurb, profile)
            try:
                reason = generate_korean_text(prompt)
            except AiProviderError:
                reason = _score_only_reason(score)
        else:
            reason = _score_only_reason(score)
        ranked.append(
            RankedJob(
                job=job,
                match_score=max(1, min(5, int(round(score * 5)))),
                reason=reason,
                semantic_score=round(score, 4),
                url_verified=None,
            )
        )

    return ranked, False, used_raw_resume_fallback
