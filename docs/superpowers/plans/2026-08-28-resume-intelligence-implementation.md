# Resume Intelligence (R → E → C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 비표준 이력서를 AI가 구조화(`ResumeProfile`)하고, 프로필 기반 공고 검색·의미 매칭(JD 한국어 blurb 포함)·팩트체크까지 **R → E → C** 파이프라인을 완성한다.

**Architecture:** `resume_analyze`가 R 레이어. `crew_runner`가 profile-driven search를 E 전단에 연결. `semantic_match`는 `matching_document` + `job_blurb`로 임베딩. Streamlit은 분석 패널 + level/position 자동 채움.

**Tech Stack:** Python 3.13, OpenAI SDK (`gpt-4o-mini` structured output), CrewAI, Streamlit, pytest

**Spec:** [2026-08-28-resume-intelligence-design.md](../specs/2026-08-28-resume-intelligence-design.md)

## Global Constraints

- Pipeline order: **R → E → C** (fixed)
- UI language / output: **한국어 (`ko`)**
- AI provider: **OpenAI primary** — `gpt-4o-mini`, `text-embedding-3-small`
- UI: **분석 후 level/position 자동 채움** (사용자 수정 시 override)
- JD blurb pre-pass: **same PR** as resume analyze
- Resume/profile: **session-scoped**; no disk persist
- Analyze failure: `used_raw_resume_fallback=True`; pipeline continues
- No hallucination: missing visa/years → `null` + `parse_warnings`
- Flat module layout at repo root (no `src/`)
- Existing 18 tests must keep passing; add 8+ new tests

## File Map (create / modify)

| File | Action | Responsibility |
|------|--------|----------------|
| `models.py` | Modify | `ResumeProfile`, extend `MvpRunResult` |
| `openai_client.py` | Modify | `generate_structured()` |
| `ai_provider.py` | Modify | facade for structured output |
| `resume_analyze.py` | Create | `analyze_resume()` |
| `job_blurb.py` | Create | JD → Korean blurb cache |
| `semantic_match.py` | Modify | profile + blurb embedding |
| `crew_runner.py` | Modify | R→E→C, profile in search |
| `config/tasks.yaml` | Modify | `{search_queries}` in extraction task |
| `app.py` | Modify | analyze UI, auto-fill, badges |
| `tests/fixtures/resumes/*.txt` | Create | fixture resumes |
| `tests/test_models.py` | Modify | ResumeProfile tests |
| `tests/test_ai_provider.py` | Modify | structured routing test |
| `tests/test_resume_analyze.py` | Create | analyze tests |
| `tests/test_job_blurb.py` | Create | blurb cache tests |
| `tests/test_semantic_match.py` | Modify | profile/blurb embed tests |
| `tests/test_crew_runner.py` | Modify | search_queries input test |
| `README.md` | Modify | R→E→C flow, score guide |

---

### Task 1: `ResumeProfile` model + `MvpRunResult` extend

**Files:**
- Modify: `models.py`
- Modify: `tests/test_models.py`

**Interfaces:**
- Produces: `ResumeProfile` with all fields from spec §5.1
- Produces: `MvpRunResult.resume_profile`, `MvpRunResult.used_raw_resume_fallback`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_models.py`:

```python
from models import ResumeProfile


def test_resume_profile_ok_status():
    profile = ResumeProfile(
        headline_ko="풀스택 3년, 일본어 네이티브",
        target_roles=["풀스택 엔지니어"],
        seniority_level="Mid",
        years_of_experience=3.0,
        skills=["Java", "GCP"],
        languages={"ko": "native", "ja": "native"},
        visa_status="취업비자",
        preferred_locations=["Tokyo"],
        search_queries_ja=["フルスタック エンジニア 東京"],
        search_queries_en=["full stack engineer Tokyo"],
        matching_document="풀스택 엔지니어, Java/GCP...",
        confidence=0.85,
        field_confidence={"skills": 0.9},
        parse_warnings=[],
        status="ok",
    )
    assert profile.status == "ok"
    assert profile.search_queries_ja[0].startswith("フル")


def test_mvp_run_result_includes_profile_fields():
    from models import ChosenJob, CompanyFactcheck, Job, MvpRunResult

    job = Job(
        job_title="Dev",
        company_name="Co",
        job_location="Tokyo",
        job_posting_url="https://example.com",
        job_summary="x",
    )
    result = MvpRunResult(
        resume_profile=None,
        ranked_jobs=[],
        chosen_job=ChosenJob(job=job, selected=True, reason="ok"),
        factcheck=CompanyFactcheck(
            corporate_number=None,
            gbiz_fields={},
            risk_tags=[],
            summary_ko="x",
            sources=[],
            status="public_unconfirmed",
        ),
        used_fallback=False,
        used_raw_resume_fallback=True,
    )
    assert result.used_raw_resume_fallback is True
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `uv run pytest tests/test_models.py -v`
Expected: `ImportError` or missing fields on `MvpRunResult`

- [ ] **Step 3: Implement models**

Add `ResumeProfile` to `models.py`. Update `MvpRunResult`:

```python
class ResumeProfile(BaseModel):
    headline_ko: str
    target_roles: list[str]
    seniority_level: str | None = None
    years_of_experience: float | None = None
    skills: list[str]
    languages: dict[str, str]
    visa_status: str | None = None
    preferred_locations: list[str]
    search_queries_ja: list[str]
    search_queries_en: list[str]
    matching_document: str
    confidence: float
    field_confidence: dict[str, float] = {}
    parse_warnings: list[str]
    status: Literal["ok", "partial", "failed"]


class MvpRunResult(BaseModel):
    resume_profile: ResumeProfile | None = None
    ranked_jobs: list[RankedJob]
    chosen_job: ChosenJob
    factcheck: CompanyFactcheck
    used_fallback: bool
    used_raw_resume_fallback: bool = False
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `uv run pytest tests/test_models.py -v`

- [ ] **Step 5: Commit**

```bash
git add models.py tests/test_models.py
git commit -m "feat: add ResumeProfile model and extend MvpRunResult"
```

---

### Task 2: `generate_structured()` in OpenAI + ai_provider

**Files:**
- Modify: `openai_client.py`
- Modify: `ai_provider.py`
- Modify: `tests/test_ai_provider.py`

**Interfaces:**
- Produces: `generate_structured(prompt: str, model_type: type[T]) -> T`
- Raises: `OpenAIClientError` / `AiProviderError`

- [ ] **Step 1: Write failing test**

Append to `tests/test_ai_provider.py`:

```python
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from ai_provider import generate_structured


class _SampleModel(BaseModel):
    name: str
    score: float


@patch("ai_provider.openai_client.generate_structured")
def test_generate_structured_routes_to_openai(mock_gen):
    mock_gen.return_value = _SampleModel(name="test", score=1.0)
    result = generate_structured("prompt", _SampleModel)
    assert result.name == "test"
    mock_gen.assert_called_once_with("prompt", _SampleModel)
```

- [ ] **Step 2: Implement `openai_client.generate_structured`**

```python
from typing import TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

def generate_structured(prompt: str, model_type: type[T]) -> T:
    try:
        model = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        response = _client().beta.chat.completions.parse(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format=model_type,
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise OpenAIClientError("Structured parse returned empty")
        return parsed
    except OpenAIClientError:
        raise
    except Exception as exc:
        raise OpenAIClientError(str(exc)) from exc
```

- [ ] **Step 3: Implement `ai_provider.generate_structured`**

```python
def generate_structured(prompt: str, model_type: type[T]) -> T:
    try:
        return openai_client.generate_structured(prompt, model_type)
    except openai_client.OpenAIClientError as exc:
        raise AiProviderError(str(exc)) from exc
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_ai_provider.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add openai_client.py ai_provider.py tests/test_ai_provider.py
git commit -m "feat: add OpenAI structured output via ai_provider"
```

---

### Task 3: `resume_analyze` module

**Files:**
- Create: `resume_analyze.py`
- Create: `tests/fixtures/resumes/freeform_ko.txt`
- Create: `tests/fixtures/resumes/minimal.txt`
- Create: `tests/test_resume_analyze.py`

**Interfaces:**
- Produces: `analyze_resume(raw_text: str) -> ResumeProfile` (never raises)
- Produces: `FAILED_PROFILE: ResumeProfile` constant for status=failed

- [ ] **Step 1: Create fixtures**

`tests/fixtures/resumes/freeform_ko.txt` — user's freeform style resume snippet.  
`tests/fixtures/resumes/minimal.txt` — short text without visa line.

- [ ] **Step 2: Write failing tests**

```python
from unittest.mock import patch

from models import ResumeProfile
from resume_analyze import FAILED_PROFILE, analyze_resume


def _ok_profile() -> ResumeProfile:
    return ResumeProfile(
        headline_ko="풀스택",
        target_roles=["풀스택 엔지니어"],
        seniority_level="Mid",
        years_of_experience=3.0,
        skills=["Java"],
        languages={"ko": "native"},
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
    text = (Path("tests/fixtures/resumes/freeform_ko.txt")).read_text(encoding="utf-8")
    profile = analyze_resume(text)
    assert profile.status == "partial"
    assert "Java" in profile.skills


@patch("resume_analyze.generate_structured", side_effect=Exception("api down"))
def test_analyze_resume_returns_failed_on_error(_mock):
    profile = analyze_resume("some resume")
    assert profile.status == "failed"
    assert profile is not None
```

Add `from pathlib import Path` at top.

- [ ] **Step 3: Implement `resume_analyze.py`**

Key logic:
- Truncate `raw_text` to 12k chars (8k head + 4k tail if longer)
- Build Korean prompt with anti-hallucination rules from spec §6.2
- Call `generate_structured(prompt, ResumeProfile)`
- On error: retry once → return `FAILED_PROFILE`
- Conditional normalize (spec §6.3): if `len < 200` or garbled heuristic, call `generate_korean_text` normalize once then re-parse

```python
FAILED_PROFILE = ResumeProfile(
    headline_ko="",
    target_roles=[],
    seniority_level=None,
    years_of_experience=None,
    skills=[],
    languages={},
    visa_status=None,
    preferred_locations=[],
    search_queries_ja=[],
    search_queries_en=[],
    matching_document="",
    confidence=0.0,
    parse_warnings=["이력서 분석 실패"],
    status="failed",
)

def analyze_resume(raw_text: str) -> ResumeProfile:
    ...
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_resume_analyze.py -v`

- [ ] **Step 5: Commit**

```bash
git add resume_analyze.py tests/test_resume_analyze.py tests/fixtures/
git commit -m "feat: add resume_analyze for ResumeProfile extraction"
```

---

### Task 4: `job_blurb` — JD Korean summary for embedding

**Files:**
- Create: `job_blurb.py`
- Create: `tests/test_job_blurb.py`

**Interfaces:**
- Produces: `build_job_blurbs(jobs: list[Job], cache: dict[str, str] | None = None) -> dict[str, str]`
  - Key: `job_posting_url`, Value: Korean 1–2 sentence blurb
- On `AiProviderError`: omit key (caller uses raw job doc)

- [ ] **Step 1: Write failing test**

```python
from unittest.mock import patch

from models import Job
from job_blurb import build_job_blurbs


@patch("job_blurb.generate_korean_text", return_value="백엔드 API 개발 포지션")
def test_build_job_blurbs_caches_by_url(mock_gen):
    job = Job(
        job_title="Backend",
        company_name="Co",
        job_location="Tokyo",
        job_posting_url="https://example.com/job/1",
        job_summary="API development",
    )
    cache: dict[str, str] = {}
    blurbs = build_job_blurbs([job, job], cache=cache)
    assert blurbs["https://example.com/job/1"] == "백엔드 API 개발 포지션"
    mock_gen.assert_called_once()
```

- [ ] **Step 2: Implement `job_blurb.py`**

```python
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
```

- [ ] **Step 3: Run tests + commit**

```bash
uv run pytest tests/test_job_blurb.py -v
git add job_blurb.py tests/test_job_blurb.py
git commit -m "feat: add Korean JD blurb builder for semantic match"
```

---

### Task 5: Update `semantic_match` for profile + blurb

**Files:**
- Modify: `semantic_match.py`
- Modify: `tests/test_semantic_match.py`

**Interfaces:**
- Consumes: `ResumeProfile | None`, `resume_text` fallback
- Change signature:

```python
def rank_jobs_semantic(
    resume_text: str,
    jobs: list[Job],
    profile: ResumeProfile | None = None,
) -> tuple[list[RankedJob], bool, bool]:
    # returns (ranked, used_openai_fallback, used_raw_resume_fallback)
```

- [ ] **Step 1: Update tests**

Mock `build_job_blurbs`, assert `embed_texts` first arg is `profile.matching_document` when profile ok.

- [ ] **Step 2: Update `build_job_document`**

```python
def build_job_document(job: Job, blurb_ko: str | None = None) -> str:
    parts = [...]
    if blurb_ko:
        parts.insert(0, f"[한국어 요약] {blurb_ko}")
    ...
```

- [ ] **Step 3: Update `rank_jobs_semantic`**

```python
use_profile = profile is not None and profile.status != "failed" and profile.matching_document.strip()
candidate_doc = profile.matching_document if use_profile else resume_text
used_raw_resume_fallback = not use_profile

blurbs = build_job_blurbs(jobs)
documents = [
    build_job_document(job, blurbs.get(job.job_posting_url))
    for job in jobs
]
```

Reason prompt uses `profile.headline_ko` and `profile.skills` when available.

- [ ] **Step 4: Run all semantic tests + commit**

```bash
uv run pytest tests/test_semantic_match.py -v
git add semantic_match.py tests/test_semantic_match.py
git commit -m "feat: semantic match uses ResumeProfile and JD blurbs"
```

---

### Task 6: Profile-driven job search in `crew_runner`

**Files:**
- Modify: `crew_runner.py`
- Modify: `config/tasks.yaml`
- Modify: `tests/test_crew_runner.py`

**Interfaces:**
- `_run_job_search(level, position, location, search_queries: str) -> JobList`
- `run_mvp(resume_text, level, position, location) -> MvpRunResult` orchestrates R→E→C:

```python
profile = analyze_resume(resume_text)
search_queries = ", ".join(profile.search_queries_ja + profile.search_queries_en)
job_list = _run_job_search(level, position, location, search_queries)
ranked, used_fallback, used_raw = rank_jobs_semantic(resume_text, job_list.jobs, profile)
```

- [ ] **Step 1: Update `config/tasks.yaml` `job_extraction_task`**

Add `{search_queries}` to description (spec §7.1).

- [ ] **Step 2: Write test for search_queries in kickoff**

Mock `JobHunterCrew` / `kickoff`; assert `inputs["search_queries"]` passed.

- [ ] **Step 3: Implement crew_runner changes**

- [ ] **Step 4: Run tests + commit**

```bash
uv run pytest tests/test_crew_runner.py -v
git add crew_runner.py config/tasks.yaml tests/test_crew_runner.py
git commit -m "feat: wire ResumeProfile into job search and R→E→C runner"
```

---

### Task 7: Streamlit UX — analyze panel + auto-fill

**Files:**
- Modify: `app.py`

**Behavior (locked):**

1. Upload → click **「이력서 분석」** button (or split from 매칭 실행)
2. Spinner “이력서 분석 중…”
3. Show `st.expander("이력서 분석 결과")` with profile fields + status badge
4. Auto-fill `st.session_state["level"]` / `["position"]` from profile
5. **「매칭 실행」** calls `run_mvp` with session values
6. Show `used_raw_resume_fallback` warning if applicable
7. Caption under score table: `0.5+ 양호 · 0.35–0.5 보통 · 0.35 미만 약함 (상대 순위 병행)`

Suggested pattern:

```python
if "profile" not in st.session_state:
    st.session_state.profile = None

if st.button("이력서 분석"):
    ...
    profile = analyze_resume(resume_text)
    st.session_state.profile = profile
    if profile.seniority_level:
        st.session_state.level = profile.seniority_level
    if profile.target_roles:
        st.session_state.position = profile.target_roles[0]
```

Use `st.text_input(..., key="level")` with session state init.

- [ ] **Step 1: Implement app.py changes**
- [ ] **Step 2: Manual smoke** — upload resume, analyze, verify auto-fill
- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: Streamlit resume analyze panel and auto-fill level/position"
```

---

### Task 8: Docs + full regression

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-08-25-korea-japan-semantic-match-factcheck-design.md` (§4 architecture: insert `[resume_analyze]`)

- [ ] **Step 1: README** — document R→E→C, analyze button, semantic_score guide
- [ ] **Step 2: Patch parent MVP spec architecture diagram**
- [ ] **Step 3: Full test suite**

Run: `uv run pytest -v`
Expected: all tests PASS (18 existing + 8+ new)

- [ ] **Step 4: Commit**

```bash
git add README.md docs/superpowers/specs/2026-08-25-korea-japan-semantic-match-factcheck-design.md
git commit -m "docs: document R→E→C pipeline and resume intelligence"
```

---

## Spec Coverage Self-Review

| Spec requirement | Task |
|------------------|------|
| `ResumeProfile` model | Task 1 |
| `generate_structured()` | Task 2 |
| `analyze_resume()` never raises | Task 3 |
| Anti-hallucination (visa null) | Task 3 test + prompt |
| Conditional normalize pass | Task 3 impl |
| Profile-driven `search_queries` | Task 6 |
| `matching_document` embedding | Task 5 |
| JD Korean blurb (same PR) | Task 4, 5 |
| `used_raw_resume_fallback` | Task 5, 6 |
| Streamlit analyze panel | Task 7 |
| Auto-fill level/position | Task 7 |
| semantic_score UI guide | Task 7 |
| Session-scoped, no persist | unchanged |
| 8+ new tests | Tasks 1–6 |

## Risks During Implementation

- `beta.chat.completions.parse` API availability — fallback to `json_schema` response_format if parse returns None
- `rank_jobs_semantic` signature change — update all callers (`crew_runner` only)
- `MvpRunResult` new required field `used_raw_resume_fallback` — update any test constructing `MvpRunResult`
- Extra OpenAI calls per run: 1 analyze + N job blurbs — acceptable for Phase 1.5; batch blurb prompt optional follow-up

## Open Items Resolved in This Plan

- UI: 분석 후 자동 채움 (separate 분석 button + session_state)
- JD blurb: same PR via `job_blurb.py`
- `rank_jobs_semantic` returns 3-tuple for fallback flags

---

**Plan complete.** Execution options:

1. **Subagent-Driven** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute in this session with executing-plans checkpoints

Which approach?
