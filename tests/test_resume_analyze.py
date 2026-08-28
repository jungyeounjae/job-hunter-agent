from pathlib import Path
from unittest.mock import patch

from models import ResumeProfile, LanguageSkill
from resume_analyze import FAILED_PROFILE, analyze_resume


def _ok_profile() -> ResumeProfile:
    return ResumeProfile(
        headline_ko="풀스택",
        target_roles=["풀스택 엔지니어"],
        seniority_level="Mid",
        years_of_experience=3.0,
        skills=["Java"],
        languages=[LanguageSkill(code="ko", level="native")],
        visa_status=None,
        preferred_locations=["Tokyo"],
        search_queries_ja=["フルスタック 東京"],
        search_queries_en=[],
        matching_document="summary",
        confidence=0.8,
        parse_warnings=["비자 정보 없음"],
        status="partial",
    )


@patch("resume_analyze.generate_structured", return_value=_ok_profile())
def test_analyze_resume_returns_profile(mock_structured):
    text = Path("tests/fixtures/resumes/freeform_ko.txt").read_text(encoding="utf-8")
    profile = analyze_resume(text)
    assert profile.status == "partial"
    assert "Java" in profile.skills
    mock_structured.assert_called()


@patch("resume_analyze.generate_structured", side_effect=Exception("api down"))
def test_analyze_resume_returns_failed_on_error(_mock):
    profile = analyze_resume("some resume")
    assert profile.status == "failed"
    assert profile is not None
    assert profile.parse_warnings == FAILED_PROFILE.parse_warnings


@patch("resume_analyze.generate_structured", return_value=_ok_profile())
def test_analyze_resume_minimal_no_visa(mock_structured):
    text = Path("tests/fixtures/resumes/minimal.txt").read_text(encoding="utf-8")
    profile = analyze_resume(text)
    assert profile.visa_status is None
    mock_structured.assert_called()
