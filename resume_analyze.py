import re

from ai_provider import AiProviderError, generate_korean_text, generate_structured
from models import ResumeProfile

MAX_CHARS = 12_000
HEAD_CHARS = 8_000
TAIL_CHARS = 4_000

FAILED_PROFILE = ResumeProfile(
    headline_ko="",
    target_roles=[],
    seniority_level=None,
    years_of_experience=None,
    skills=[],
    languages=[],
    visa_status=None,
    preferred_locations=[],
    search_queries_ja=[],
    search_queries_en=[],
    matching_document="",
    confidence=0.0,
    parse_warnings=["이력서 분석 실패"],
    status="failed",
)

_SYSTEM_PROMPT = """당신은 한국→일본 취업 코치이자 이력서 파서입니다.
이력서 텍스트에서 사실만 추출해 JSON 스키마에 맞게 반환하세요.

규칙:
- 텍스트에 없는 비자·경력년수·학력은 추정하지 말고 null 또는 빈 리스트로 두세요.
- languages는 [{"code": "ko", "level": "native"}, {"code": "ja", "level": "business"}] 형식의 리스트입니다.
- 불명확한 필드는 parse_warnings에 이유를 적으세요.
- matching_document는 한국어 중심으로 스킬·경력·희망직무·언어를 문단 형태로 재구성하세요 (4000자 이내).
- 일본 취업 검색용 search_queries_ja는 1–3개 일본어 키워드를 생성하세요.
- search_queries_en은 0–2개 영어 키워드.
- confidence는 0.0–1.0 전체 추출 신뢰도.
- status: ok(대부분 확실), partial(일부 미확인), failed(분석 불가).
"""


def _truncate_text(raw_text: str) -> str:
    text = raw_text.strip()
    if len(text) <= MAX_CHARS:
        return text
    return text[:HEAD_CHARS] + "\n...\n" + text[-TAIL_CHARS:]


def _is_garbled(text: str) -> bool:
    if not text.strip():
        return True
    whitespace_ratio = len(re.findall(r"\s", text)) / max(len(text), 1)
    newline_ratio = text.count("\n") / max(len(text), 1)
    return whitespace_ratio > 0.6 or newline_ratio > 0.15


def _needs_normalize(raw_text: str) -> bool:
    return len(raw_text.strip()) < 200 or _is_garbled(raw_text)


def _build_prompt(raw_text: str) -> str:
    return (
        f"{_SYSTEM_PROMPT}\n\n"
        f"[이력서]\n{_truncate_text(raw_text)}\n\n"
        "위 이력서를 분석해 ResumeProfile JSON을 반환하세요."
    )


def _try_parse(raw_text: str) -> ResumeProfile | None:
    try:
        return generate_structured(_build_prompt(raw_text), ResumeProfile)
    except (AiProviderError, Exception):
        return None


def _normalize_text(raw_text: str) -> str:
    prompt = (
        "다음 이력서 텍스트를 읽기 쉬운 한국어 정리본으로 재구성하세요. "
        "사실만 유지하고, 섹션(경력, 스킬, 희망직무 등)을 명확히 하세요.\n\n"
        f"{raw_text[:8000]}"
    )
    try:
        return generate_korean_text(prompt)
    except AiProviderError:
        return raw_text


def analyze_resume(raw_text: str) -> ResumeProfile:
    text = raw_text.strip()
    if not text:
        return FAILED_PROFILE

    if _needs_normalize(text):
        text = _normalize_text(text)

    profile = _try_parse(text)
    if profile is None:
        profile = _try_parse(text)
    if profile is None:
        return FAILED_PROFILE

    if profile.status == "partial" and profile.confidence < 0.5:
        normalized = _normalize_text(text)
        retry = _try_parse(normalized)
        if retry is not None:
            profile = retry

    return profile
