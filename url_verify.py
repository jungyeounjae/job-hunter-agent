import httpx

from models import RankedJob


def verify_job_url(url: str, cache: dict[str, bool] | None = None) -> bool:
    if cache is not None and url in cache:
        return cache[url]
    ok = False
    try:
        response = httpx.head(url, follow_redirects=True, timeout=10.0)
        ok = response.status_code < 400
        if response.status_code == 405:
            response = httpx.get(url, follow_redirects=True, timeout=10.0)
            ok = response.status_code < 400
    except httpx.HTTPError:
        ok = False
    if cache is not None:
        cache[url] = ok
    return ok


def apply_url_verification(
    ranked_jobs: list[RankedJob],
    cache: dict[str, bool] | None = None,
) -> list[RankedJob]:
    updated: list[RankedJob] = []
    for item in ranked_jobs:
        verified = verify_job_url(item.job.job_posting_url, cache=cache)
        updated.append(item.model_copy(update={"url_verified": verified}))
    updated.sort(
        key=lambda r: (
            1 if r.url_verified else 0,
            r.semantic_score or 0.0,
        ),
        reverse=True,
    )
    return updated
