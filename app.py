import importlib
import inspect

import dotenv
import streamlit as st

dotenv.load_dotenv()

import crew_runner
import main as crew_main
import tools

importlib.reload(tools)
importlib.reload(crew_main)
importlib.reload(crew_runner)
from japan_prefectures import JAPAN_PREFECTURES, match_prefecture
from resume_analyze import analyze_resume
from resume_ingest import TEMPLATE_PATH, UnsupportedResumeFormatError, parse_resume_bytes


def _call_run_mvp(resume_text: str, prefecture: str, on_progress=None):
    """Streamlit dev reload/cache와 구 시그니처 모두 대응."""
    fn = crew_runner.run_mvp
    sig = inspect.signature(fn)
    if "on_progress" in sig.parameters:
        return fn(resume_text, prefecture, on_progress=on_progress)
    if "prefecture" in sig.parameters:
        return fn(resume_text, prefecture)
    return fn(resume_text, "Mid", "Engineer", prefecture)


st.set_page_config(page_title="일본 취업 매칭", layout="wide")
st.title("일본 취업 — 이력서 분석 · 의미 매칭")


def _fmt_unknown_bool(value: bool | None) -> str:
    if value is None:
        return "미확인"
    return "예" if value else "아니오"


if "profile" not in st.session_state:
    st.session_state.profile = None
if "resume_text" not in st.session_state:
    st.session_state.resume_text = None
if "prefecture" not in st.session_state:
    st.session_state.prefecture = None

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
            if profile.preferred_locations:
                guessed = match_prefecture(*profile.preferred_locations)
                if guessed:
                    st.session_state.prefecture = guessed

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
        if profile.seniority_level:
            st.write(f"**레벨 (AI 추출):** {profile.seniority_level}")
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

st.selectbox(
    "근무 희망 도도부현 *",
    options=JAPAN_PREFECTURES,
    index=None,
    placeholder="도도부현을 선택하세요 (필수)",
    key="prefecture",
)

run = st.button("매칭 실행", type="primary")

if run:
    if st.session_state.resume_text is None:
        st.error("이력서 파일을 업로드해 주세요. 템플릿을 다운로드해 작성할 수 있습니다.")
        st.stop()
    if not st.session_state.prefecture:
        st.error("근무 희망 도도부현을 선택해 주세요.")
        st.stop()

    with st.status("매칭 진행 중…", expanded=True) as status:

        def _progress(message: str) -> None:
            status.update(label=message)

        try:
            result = _call_run_mvp(
                st.session_state.resume_text,
                st.session_state.prefecture,
                on_progress=_progress,
            )
        except ValueError as exc:
            status.update(label="실패", state="error")
            st.warning(str(exc))
            st.stop()

        status.update(label="매칭 완료", state="complete")

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
        "상위 5건만 LLM 매칭 이유 생성 · 나머지는 유사도 점수만 표시. "
        "해외지원/비자/일본어 '미확인'은 공고에 명시 없음 — 제외 사유 아님."
    )

    chosen = result.chosen_job.job
    st.subheader("선정 공고")
    st.write(f"**{chosen.company_name}** — {chosen.job_title}")
    st.write(f"**선정 이유:** {result.chosen_job.reason}")
    st.write(f"**근무지:** {chosen.job_location}")
    st.link_button("공고 보기", chosen.job_posting_url)
    st.caption("공개 채용 공고는 게시된 채용 플랫폼·기업 채널을 신뢰 근거로 합니다.")
