from ai_provider import AiProviderError, generate_korean_text
from gbiz_client import search_corporation
from models import CompanyFactcheck


def build_factcheck(company_name: str, job_url: str) -> CompanyFactcheck:
    record = search_corporation(company_name)
    if not record:
        summary = "공공 DB에서 법인을 확인하지 못했습니다."
        try:
            summary = generate_korean_text(
                f"일본 회사 '{company_name}' 공고 URL: {job_url}. "
                "gBizINFO에서 법인을 찾지 못했습니다. 한국어로 리스크 요약 3문장."
            )
        except AiProviderError:
            pass
        return CompanyFactcheck(
            corporate_number=None,
            gbiz_fields={},
            risk_tags=["공공_미확인"],
            summary_ko=summary,
            sources=[job_url],
            status="public_unconfirmed",
        )

    corp_no = record.get("corporate_number")
    gbiz_fields = {k: v for k, v in record.items() if v is not None}
    prompt = (
        f"다음 일본 법인 공공 데이터를 바탕으로 한국 구직자에게 기업 신뢰도를 "
        f"한국어 4문장으로 요약하세요. 과장하지 마세요.\n\n{gbiz_fields}"
    )
    try:
        summary = generate_korean_text(prompt)
    except AiProviderError:
        summary = f"gBizINFO에서 {record.get('name', company_name)} 법인 정보를 확인했습니다."

    risk_tags: list[str] = []
    if not corp_no:
        risk_tags.append("법인번호_없음")

    return CompanyFactcheck(
        corporate_number=corp_no,
        gbiz_fields=gbiz_fields,
        risk_tags=risk_tags,
        summary_ko=summary,
        sources=["gBizINFO", job_url],
        status="verified",
    )
