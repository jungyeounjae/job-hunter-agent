from unittest.mock import patch

from models import Job, ResumeProfile, LanguageSkill
from semantic_match import cosine_similarity, rank_jobs_semantic


def test_cosine_similarity_identical():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_orthogonal():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


@patch("semantic_match.generate_korean_text", return_value="일본 백엔드 경험과 일치")
@patch("semantic_match.build_job_blurbs", return_value={})
@patch("semantic_match.embed_texts")
def test_rank_jobs_semantic_orders_by_score(mock_embed, _mock_blurbs, _mock_reason):
    mock_embed.return_value = [
        [1.0, 0.0],  # resume
        [0.9, 0.1],  # job A
        [0.1, 0.9],  # job B
    ]
    jobs = [
        Job(
            job_title="A",
            company_name="CoA",
            job_location="Tokyo",
            job_posting_url="https://a.example/job",
            job_summary="backend",
        ),
        Job(
            job_title="B",
            company_name="CoB",
            job_location="Tokyo",
            job_posting_url="https://b.example/job",
            job_summary="design",
        ),
    ]
    ranked, used_fallback, used_raw = rank_jobs_semantic("resume text", jobs)
    assert used_fallback is False
    assert used_raw is True
    assert ranked[0].job.job_title == "A"
    assert ranked[0].semantic_score >= ranked[1].semantic_score
    assert ranked[0].reason == "일본 백엔드 경험과 일치"


def _sample_profile() -> ResumeProfile:
    return ResumeProfile(
        headline_ko="백엔드 5년",
        target_roles=["백엔드 엔지니어"],
        seniority_level="Senior",
        years_of_experience=5.0,
        skills=["Python", "AWS"],
        languages=[LanguageSkill(code="ko", level="native")],
        visa_status=None,
        preferred_locations=["Tokyo"],
        search_queries_ja=["バックエンド 東京"],
        search_queries_en=[],
        matching_document="백엔드 엔지니어 5년, Python/AWS",
        confidence=0.9,
        parse_warnings=[],
        status="ok",
    )


@patch("semantic_match.generate_korean_text", return_value="프로필 기반 매칭")
@patch("semantic_match.build_job_blurbs", return_value={"https://a.example/job": "백엔드 API"})
@patch("semantic_match.embed_texts")
def test_rank_jobs_semantic_uses_matching_document(mock_embed, _mock_blurbs, _mock_reason):
    mock_embed.return_value = [[1.0, 0.0], [0.8, 0.2]]
    jobs = [
        Job(
            job_title="A",
            company_name="CoA",
            job_location="Tokyo",
            job_posting_url="https://a.example/job",
            job_summary="backend",
        ),
    ]
    profile = _sample_profile()
    rank_jobs_semantic("raw resume text", jobs, profile=profile)
    embed_args = mock_embed.call_args[0][0]
    assert embed_args[0] == profile.matching_document
