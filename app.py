import dotenv
import streamlit as st

dotenv.load_dotenv()

from crew_runner import run_mvp
from resume_analyze import analyze_resume
from resume_ingest import TEMPLATE_PATH, UnsupportedResumeFormatError, parse_resume_bytes


st.set_page_config(page_title="일본 취업 매칭", layout="wide")
st.title("일본 취업 — 이력서 분석 · 의미 매칭 · 기업 팩트체크")


def _fmt_unknown_bool(value: bool | None) -> str:
    if value is None:
        return "미확인"
    return "예" if value else "아니오"

if "profile" not in st.session_state:
    st.session_state.profile = None
if "resume_text" not in st.session_state:
    st.session_state.resume_text = None
if "level" not in st.session_state:
    st.session_state.level = "Senior"
if "position" not in st.session_state:
    st.session_state.position = "Backend Engineer"
if "location" not in st.session_state:
    st.session_state.location = "Japan"

with st.expander("직무이력서 템플릿", expanded=True):
    template_bytes = TEMPLATE_PATH.read_bytes()
    st.download_button(
        label="직무이력서 템플릿 다운로드 (.md)",
        data=template_bytes,
        file_name="직무이력서_템플릿.md",
        mime="text/markdown",
    )

uploaded = st.file_uploader(
    "작성한 직무이력서 업로드 (PDF / DOCX / TXT / MD)",
    type=["pdf", "docx", "txt", "md"],
)

if uploaded is not None:
    try:
        st.session_state.resume_text = parse_resume_bytes(uploaded.getvalue(), uploaded.name)
    except (UnsupportedResumeFormatError, ValueError) as exc:
        st.error(f"이력서를 읽을 수 없습니다: {exc}")
        st.session_state.resume_text = None

if st.button("이력서 분석", type="secondary"):
    if st.session_state.resume_text is None:
        st.error("이력서 파일을 업로드해 주세요.")
    else:
        with st.spinner("이력서 분석 중…"):
            profile = analyze_resume(st.session_state.resume_text)
            st.session_state.profile = profile
            if profile.seniority_level:
                st.session_state.level = profile.seniority_level
            if profile.target_roles:
                st.session_state.position = profile.target_roles[0]

profile = st.session_state.profile
if profile is not None:
    status_labels = {
        "ok": "🟢 분석 완료",
        "partial": "🟡 일부 항목 미확인",
        "failed": "🟠 원문 기반 매칭 (품질↓)",
    }
    with st.expander("이력서 분석 결과", expanded=True):
        st.write(f"**상태:** {status_labels.get(profile.status, profile.status)}")
        st.write(f"**요약:** {profile.headline_ko or '(없음)'}")
        if profile.target_roles:
            st.write(f"**희망 직무:** {', '.join(profile.target_roles)}")
        if profile.skills:
            st.write(f"**스킬:** {', '.join(profile.skills)}")
        if profile.languages:
            langs = ", ".join(f"{lang.code}: {lang.level}" for lang in profile.languages)
            st.write(f"**언어:** {langs}")
        if profile.visa_status:
            st.write(f"**비자:** {profile.visa_status}")
        if profile.search_queries_ja:
            st.write(f"**일본어 검색어:** {', '.join(profile.search_queries_ja)}")
        if profile.search_queries_en:
            st.write(f"**영어 검색어:** {', '.join(profile.search_queries_en)}")
        if profile.parse_warnings:
            st.warning("주의: " + "; ".join(profile.parse_warnings))
        st.caption(f"분석 신뢰도: {profile.confidence:.0%} (AI 추출 결과)")

col1, col2, col3 = st.columns(3)
with col1:
    st.text_input("레벨", key="level")
with col2:
    st.text_input("포지션", key="position")
with col3:
    st.text_input("근무지", key="location")

run = st.button("매칭 실행", type="primary")

if run:
    if st.session_state.resume_text is None:
        st.error("이력서 파일을 업로드해 주세요. 템플릿을 다운로드해 작성할 수 있습니다.")
        st.stop()

    with st.spinner("일본 공고 검색 및 매칭 중..."):
        try:
            result = run_mvp(
                st.session_state.resume_text,
                st.session_state.level,
                st.session_state.position,
                st.session_state.location,
            )
        except ValueError as exc:
            st.warning(str(exc))
            st.stop()

    if result.used_fallback:
        st.warning("품질↓ OpenAI 장애로 기본 매칭으로 전환되었습니다.")
    if result.used_raw_resume_fallback:
        st.warning("품질↓ 이력서 분석 실패로 원문 기반 매칭을 사용했습니다.")
    if result.run_artifact_dir:
        st.caption(f"실행 아티팩트: `{result.run_artifact_dir}` (inputs/result/manifest.json)")

    rows = []
    for r in result.ranked_jobs:
        rows.append(
            {
                "회사": r.job.company_name,
                "직무": r.job.job_title,
                "semantic_score": r.semantic_score,
                "해외지원": _fmt_unknown_bool(r.job.overseas_applicable),
                "비자스폰서": _fmt_unknown_bool(r.job.visa_support),
                "일본어": r.job.japanese_level or "미확인",
                "url_verified": r.url_verified,
                "이유": r.reason,
                "링크": r.job.job_posting_url,
            }
        )
    st.subheader("매칭 결과")
    st.dataframe(rows, use_container_width=True)
    st.caption(
        "semantic_score: 0.5+ 양호 · 0.35–0.5 보통 · 0.35 미만 약함 (상대 순위 병행). "
        "해외지원/비자/일본어 '미확인'은 공고에 명시 없음 — 제외 사유 아님."
    )

    st.subheader("선정 기업 팩트체크")
    fc = result.factcheck
    st.write(f"**상태:** {fc.status}")
    if fc.corporate_number:
        st.write(f"**法人番号:** {fc.corporate_number}")
    if fc.risk_tags:
        st.write(f"**리스크 태그:** {', '.join(fc.risk_tags)}")
    st.write(fc.summary_ko)
    st.caption("출처: " + ", ".join(fc.sources))

    md = (
        f"# 기업 팩트체크\n\n"
        f"- 상태: {fc.status}\n"
        f"- 法人番号: {fc.corporate_number or 'N/A'}\n\n"
        f"## 요약\n{fc.summary_ko}\n\n"
        f"## 출처\n" + "\n".join(f"- {s}" for s in fc.sources)
    )
    st.download_button(
        label="팩트체크 Markdown 다운로드",
        data=md.encode("utf-8"),
        file_name="company_factcheck.md",
        mime="text/markdown",
    )
