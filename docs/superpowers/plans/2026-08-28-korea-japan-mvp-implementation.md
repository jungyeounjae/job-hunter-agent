# Korea→Japan MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Streamlit UI에서 한국 구직자가 이력서를 업로드하고, 일본 공고 의미 매칭(E)과 기업 팩트체크(C) 결과를 한국어로 받을 수 있는 MVP 파이프라인을 구현한다.

**Architecture:** CrewAI job search/selection 유지. `semantic_match`·`company_factcheck`는 **`ai_provider` 파사드**를 통해 **OpenAI(Phase 1 primary)** 호출. Vertex는 Phase 2에서 `ai_provider`에 추가.

**Tech Stack:** Python 3.13, CrewAI, Streamlit, Firecrawl, OpenAI SDK, gBizINFO, pytest, pypdf, python-docx  
*(Phase 2 추가: `google-cloud-aiplatform`, Vertex Vector Search, Grounding)*

**Spec:** [2026-08-25-korea-japan-semantic-match-factcheck-design.md](../specs/2026-08-25-korea-japan-semantic-match-factcheck-design.md)

## Global Constraints

- Target users: 한국→일본 취업 희망 구직자; UI/출력 언어: **한국어 (`ko`)**
- MVP scope: search → semantic match → selection → company fact-check only (resume rewrite / interview prep 제외)
- **Phase 1 AI provider:** **`openai`** — `text-embedding-3-small`, `gpt-4o-mini` (user subscription)
- **Phase 2 AI provider:** **`vertex`** — `text-embedding-005`, `gemini-2.0-flash-001` (GCP project + ADC); provider switch in Streamlit
- **Phase 1 fallback:** OpenAI failure → CrewAI LLM matching; UI shows “품질↓”
- **Phase 2 fallback:** primary provider fails → alternate if configured → CrewAI LLM
- Default location: **`Japan`**
- Ranking: primary **`semantic_score`**, demote/exclude when **`url_verified=False`**
- Fact-check scope: **`ChosenJob` only** (non-selected jobs: no fact-check in MVP)
- Template format: **`.md`** at `knowledge/templates/직무이력서_템플릿.md`
- Uploaded resume: **session-scoped temp**; do not persist to `knowledge/resume.txt` by default
- Hello Work API: **not in MVP**
- Keep `output/` and personal resumes gitignored
- Existing flat module layout (`models.py`, `tools.py` at repo root) — do not introduce `src/` package unless a file exceeds ~200 lines

## File Map (create / modify)

| File | Action | Responsibility |
|------|--------|----------------|
| `pyproject.toml` | Modify | Add streamlit, openai, httpx, pypdf, python-docx, pytest |
| `.env.example` | Modify | OpenAI + gBizINFO (Vertex vars commented as Phase 2) |
| `openai_client.py` | Create | OpenAI embeddings + chat |
| `ai_provider.py` | Create | Facade: OpenAI primary; Phase 2 adds Vertex routing |
| `vertex_client.py` | — | **Phase 2** — defer until Vertex integration |
| `semantic_match.py` | Create | Uses `ai_provider`, not clients directly |
| `company_factcheck.py` | Create | Uses `ai_provider` |
| `crew_runner.py` | Create | MVP orchestration; temp resume file |
| `main.py` | Modify | Extract crew class; guard CLI entrypoint |
| `config/agents.yaml` | Modify | Add `company_factcheck_agent` (optional) or keep Python-only |
| `config/tasks.yaml` | Modify | Add semantic match task description (if Crew task used) |
| `app.py` | Create | Streamlit UI |
| `tests/test_resume_ingest.py` | Create | Ingest tests |
| `tests/test_semantic_match.py` | Create | Cosine + ranking tests (mocked Vertex) |
| `tests/test_url_verify.py` | Create | URL verification tests |
| `tests/test_gbiz_client.py` | Create | gBiz parse tests (mocked HTTP) |
| `tests/test_company_factcheck.py` | Create | Status mapping tests |
| `README.md` | Modify | Streamlit run, GCP setup, gBizINFO |

---

### Task 1: Test harness and dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Create: `tests/conftest.py`

**Interfaces:**
- Produces: pytest runnable via `uv run pytest`; env var names documented

- [ ] **Step 1: Add dependencies to `pyproject.toml`**

```toml
[project]
dependencies = [
    "crewai[tools]>=0.152.0",
    "firecrawl-py>=2.16.3",
    "python-dotenv>=1.1.1",
    "streamlit>=1.41.0",
    "openai>=1.58.0",
    "httpx>=0.28.0",
    "pypdf>=5.1.0",
    "python-docx>=1.1.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-mock>=3.14.0",
]
```

- [ ] **Step 2: Sync dependencies**

Run: `uv sync --extra dev`
Expected: lockfile updated, no resolution errors

- [ ] **Step 3: Extend `.env.example`**

```env
OPENAI_API_KEY=your-openai-api-key
SERPER_API_KEY=your-serper-api-key
FIRECRAWL_API_KEY=your-firecrawl-api-key

# Phase 1 (MVP) — OpenAI primary
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o-mini

GBIZINFO_API_TOKEN=your-gbizinfo-api-token

# Phase 2 — Vertex AI (optional; uncomment when integrating)
# AI_PROVIDER=vertex
# GOOGLE_CLOUD_PROJECT=your-gcp-project-id
# GOOGLE_CLOUD_LOCATION=asia-northeast1
# VERTEX_EMBEDDING_MODEL=text-embedding-005
# VERTEX_GEMINI_MODEL=gemini-2.0-flash-001
```

- [ ] **Step 4: Create minimal pytest conftest**

Create `tests/conftest.py`:

```python
import os
import pytest


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
```

- [ ] **Step 5: Verify pytest runs**

Run: `uv run pytest --collect-only`
Expected: `no tests ran` or empty collection (0 tests) — no import errors

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .env.example tests/conftest.py
git commit -m "chore: add MVP dependencies and pytest harness"
```

---

### Task 2: Extend Pydantic models

**Files:**
- Modify: `models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `RankedJob.semantic_score: float | None`
  - `RankedJob.url_verified: bool | None`
  - `CompanyFactcheck` with fields from spec §5.2
  - `MvpRunResult(ranked_jobs, chosen_job, factcheck, used_fallback: bool)`

- [ ] **Step 1: Write failing model tests**

Create `tests/test_models.py`:

```python
from models import CompanyFactcheck, MvpRunResult, RankedJob, Job, ChosenJob


def test_ranked_job_accepts_semantic_fields():
    job = Job(
        job_title="Backend Engineer",
        company_name="Example KK",
        job_location="Tokyo",
        job_posting_url="https://example.com/job/1",
        job_summary="Build APIs",
    )
    ranked = RankedJob(
        job=job,
        match_score=4,
        reason="Good fit",
        semantic_score=0.82,
        url_verified=True,
    )
    assert ranked.semantic_score == 0.82
    assert ranked.url_verified is True


def test_company_factcheck_status_literal():
    fc = CompanyFactcheck(
        corporate_number="1234567890123",
        gbiz_fields={"name": "Example KK"},
        risk_tags=["소규모"],
        summary_ko="공공 데이터 확인됨",
        sources=["gBizINFO"],
        status="verified",
    )
    assert fc.status == "verified"


def test_mvp_run_result_shape():
    job = Job(
        job_title="PM",
        company_name="Acme",
        job_location="Osaka",
        job_posting_url="https://example.com/job/2",
        job_summary="Lead product",
    )
    chosen = ChosenJob(job=job, selected=True, reason="Best match")
    fc = CompanyFactcheck(
        corporate_number=None,
        gbiz_fields={},
        risk_tags=[],
        summary_ko="미확인",
        sources=[],
        status="public_unconfirmed",
    )
    result = MvpRunResult(
        ranked_jobs=[],
        chosen_job=chosen,
        factcheck=fc,
        used_fallback=False,
    )
    assert result.used_fallback is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL — `ImportError` or missing fields on `RankedJob`

- [ ] **Step 3: Implement model changes**

Modify `models.py` — append after `ChosenJob`:

```python
from typing import Literal


class RankedJob(BaseModel):
    job: Job
    match_score: int
    reason: str
    semantic_score: float | None = None
    url_verified: bool | None = None


class CompanyFactcheck(BaseModel):
    corporate_number: str | None
    gbiz_fields: dict
    risk_tags: list[str]
    summary_ko: str
    sources: list[str]
    status: Literal["verified", "public_unconfirmed", "error"]


class MvpRunResult(BaseModel):
    ranked_jobs: list[RankedJob]
    chosen_job: ChosenJob
    factcheck: CompanyFactcheck
    used_fallback: bool
```

Update the existing `RankedJob` class in place (do not duplicate).

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add models.py tests/test_models.py
git commit -m "feat: extend models for semantic match and fact-check MVP"
```

---

### Task 3: Resume ingest and template

**Files:**
- Create: `resume_ingest.py`
- Create: `knowledge/templates/직무이력서_템플릿.md`
- Create: `tests/test_resume_ingest.py`

**Interfaces:**
- Produces:
  - `TEMPLATE_PATH: Path` → `knowledge/templates/직무이력서_템플릿.md`
  - `parse_resume_bytes(data: bytes, filename: str) -> str`
  - `UnsupportedResumeFormatError(Exception)`

- [ ] **Step 1: Write failing ingest tests**

Create `tests/test_resume_ingest.py`:

```python
import pytest
from resume_ingest import TEMPLATE_PATH, parse_resume_bytes, UnsupportedResumeFormatError


def test_template_path_exists():
    assert TEMPLATE_PATH.exists()
    assert TEMPLATE_PATH.suffix == ".md"


def test_parse_txt_utf8():
    text = parse_resume_bytes("안녕하세요\n경력 3년".encode("utf-8"), "resume.txt")
    assert "경력 3년" in text


def test_parse_unsupported_extension():
    with pytest.raises(UnsupportedResumeFormatError):
        parse_resume_bytes(b"data", "resume.xlsx")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_resume_ingest.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create template file**

Create `knowledge/templates/직무이력서_템플릿.md`:

```markdown
# 직무이력서 (일본 취업용 — 한국어 작성)

## 기본 정보
- 이름:
- 이메일:
- 희망 직무:
- 희망 근무지 (일본):

## 요약
(3–5문장)

## 경력
### 회사명 / 기간 / 직함
- 성과 1
- 성과 2

## 기술 스택
- 

## 학력
- 

## 언어
- 한국어:
- 일본어:
- 영어:

## 비자·취업 관련 (선택)
- 현재 비자:
- 일본 취업 가능 시점:
```

- [ ] **Step 4: Implement `resume_ingest.py`**

```python
from pathlib import Path
import io

from docx import Document
from pypdf import PdfReader


TEMPLATE_PATH = Path("knowledge/templates/직무이력서_템플릿.md")


class UnsupportedResumeFormatError(ValueError):
    pass


def parse_resume_bytes(data: bytes, filename: str) -> str:
    name = filename.lower()
    if name.endswith((".txt", ".md")):
        return data.decode("utf-8").strip()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
        if not text:
            raise ValueError("PDF에서 텍스트를 추출하지 못했습니다.")
        return text
    if name.endswith(".docx"):
        doc = Document(io.BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs).strip()
        if not text:
            raise ValueError("DOCX에서 텍스트를 추출하지 못했습니다.")
        return text
    raise UnsupportedResumeFormatError(f"지원하지 않는 형식: {filename}")
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_resume_ingest.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add resume_ingest.py knowledge/templates/직무이력서_템플릿.md tests/test_resume_ingest.py
git commit -m "feat: add resume ingest and Korean career template"
```

---

### Task 4: OpenAI client + provider facade (Phase 1)

**Files:**
- Create: `openai_client.py`
- Create: `ai_provider.py`
- Create: `tests/test_ai_provider.py`

**Interfaces:**
- Produces:
  - `embed_texts(texts: list[str]) -> list[list[float]]`
  - `generate_korean_text(prompt: str) -> str`
  - `AiProviderError(Exception)`

**Implementation notes:**
- `openai_client.py`: use `OpenAI().embeddings.create(model=OPENAI_EMBEDDING_MODEL)` and `chat.completions.create(model=OPENAI_CHAT_MODEL)`
- `ai_provider.py`: Phase 1 wraps `openai_client` only; on failure raise `AiProviderError` (caller falls back to CrewAI LLM)
- **Phase 2 follow-up:** add `vertex_client.py`, `AI_PROVIDER` routing, cross-provider fallback

- [ ] **Step 1: Write failing provider test**

Create `tests/test_ai_provider.py`:

```python
from unittest.mock import patch

from ai_provider import embed_texts, generate_korean_text


@patch("ai_provider.openai_client.embed_texts", return_value=[[1.0, 0.0]])
def test_embed_routes_to_openai(mock_oai):
    assert embed_texts(["hello"]) == [[1.0, 0.0]]
    mock_oai.assert_called_once()


@patch("ai_provider.openai_client.generate_korean_text", return_value="한국어 이유")
def test_generate_korean_text_routes_to_openai(mock_oai):
    assert generate_korean_text("prompt") == "한국어 이유"
    mock_oai.assert_called_once()
```

- [ ] **Step 2–4:** Implement `openai_client.py` and `ai_provider.py`, run tests, commit as `feat: add OpenAI provider facade for MVP`

> **Note:** Tasks 5–7 import from `ai_provider`, not `openai_client` directly.

### Task 4 (Phase 2 — Vertex integration, deferred)

When adding Vertex in Phase 2:
- Create `vertex_client.py` + extend `ai_provider.py` with `AI_PROVIDER` routing
- Add `google-cloud-aiplatform` to `pyproject.toml`
- Add Streamlit sidebar provider selector
- Add cross-provider fallback tests

The legacy Vertex-only block below is **reference only** for Phase 2:

```python
from unittest.mock import MagicMock, patch

from vertex_client import embed_texts, generate_korean_text


@patch("vertex_client._embedding_model")
def test_embed_texts_returns_vectors(mock_model):
    mock_model.get_embeddings.return_value = [
        MagicMock(values=[1.0, 0.0]),
        MagicMock(values=[0.0, 1.0]),
    ]
    vectors = embed_texts(["resume", "job"])
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]


@patch("vertex_client._generative_model")
def test_generate_korean_text(mock_model):
    mock_model.generate_content.return_value = MagicMock(text="한국어 이유")
    assert generate_korean_text("prompt") == "한국어 이유"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_vertex_client.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `vertex_client.py`**

```python
import os

import vertexai
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingModel


class VertexClientError(RuntimeError):
    pass


def _init_vertex() -> None:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-northeast1")
    if not project:
        raise VertexClientError("GOOGLE_CLOUD_PROJECT is not set")
    vertexai.init(project=project, location=location)


def _embedding_model() -> TextEmbeddingModel:
    _init_vertex()
    model_name = os.environ.get("VERTEX_EMBEDDING_MODEL", "text-embedding-005")
    return TextEmbeddingModel.from_pretrained(model_name)


def _generative_model() -> GenerativeModel:
    _init_vertex()
    model_name = os.environ.get("VERTEX_GEMINI_MODEL", "gemini-2.0-flash-001")
    return GenerativeModel(model_name)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    try:
        model = _embedding_model()
        embeddings = model.get_embeddings(texts)
        return [list(e.values) for e in embeddings]
    except Exception as exc:
        raise VertexClientError(str(exc)) from exc


def generate_korean_text(prompt: str) -> str:
    try:
        model = _generative_model()
        response = model.generate_content(prompt)
        text = getattr(response, "text", None) or str(response)
        return text.strip()
    except Exception as exc:
        raise VertexClientError(str(exc)) from exc
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_vertex_client.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add vertex_client.py tests/test_vertex_client.py
git commit -m "feat: add Vertex embedding and Gemini client"
```

---

### Task 5: Semantic match service

**Files:**
- Create: `semantic_match.py`
- Create: `tests/test_semantic_match.py`

**Interfaces:**
- Consumes: `embed_texts`, `generate_korean_text` from `ai_provider`; `Job`, `RankedJob` from `models`
- Produces:
  - `cosine_similarity(a: list[float], b: list[float]) -> float`
  - `build_job_document(job: Job) -> str`
  - `rank_jobs_semantic(resume_text: str, jobs: list[Job]) -> tuple[list[RankedJob], bool]`
    - Returns `(ranked_jobs sorted by semantic_score desc, used_fallback: bool)`

- [ ] **Step 1: Write failing tests**

Create `tests/test_semantic_match.py`:

```python
from unittest.mock import patch

from models import Job
from semantic_match import cosine_similarity, rank_jobs_semantic


def test_cosine_similarity_identical():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_orthogonal():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


@patch("semantic_match.generate_korean_text", return_value="일본 백엔드 경험과 일치")
@patch("semantic_match.embed_texts")
def test_rank_jobs_semantic_orders_by_score(mock_embed, _mock_reason):
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
    ranked, used_fallback = rank_jobs_semantic("resume text", jobs)
    assert used_fallback is False
    assert ranked[0].job.job_title == "A"
    assert ranked[0].semantic_score >= ranked[1].semantic_score
    assert ranked[0].reason == "일본 백엔드 경험과 일치"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_semantic_match.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `semantic_match.py`**

```python
import math

from models import Job, RankedJob
from ai_provider import AiProviderError, embed_texts, generate_korean_text


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_job_document(job: Job) -> str:
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
    return "\n".join(p for p in parts if p)


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


def rank_jobs_semantic(resume_text: str, jobs: list[Job]) -> tuple[list[RankedJob], bool]:
    if not jobs:
        return [], False

    documents = [build_job_document(job) for job in jobs]
    try:
        vectors = embed_texts([resume_text, *documents])
    except AiProviderError:
        return _fallback_rank(jobs), True

    resume_vec = vectors[0]
    ranked: list[RankedJob] = []
    for job, job_vec, doc in zip(jobs, vectors[1:], documents):
        score = cosine_similarity(resume_vec, job_vec)
        prompt = (
            "당신은 한국→일본 취업 코치입니다. 아래 이력서와 일본 채용공고의 "
            f"의미적 유사도는 {score:.2f}입니다. 한국어로 2문장 이내 매칭 이유를 작성하세요.\n\n"
            f"[이력서]\n{resume_text[:2000]}\n\n[공고]\n{doc[:2000]}"
        )
        try:
            reason = generate_korean_text(prompt)
        except AiProviderError:
            reason = f"의미 유사도 {score:.2f}"
        ranked.append(
            RankedJob(
                job=job,
                match_score=max(1, min(5, int(round(score * 5)))),
                reason=reason,
                semantic_score=round(score, 4),
                url_verified=None,
            )
        )

    ranked.sort(key=lambda r: r.semantic_score or 0.0, reverse=True)
    return ranked, False
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_semantic_match.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add semantic_match.py tests/test_semantic_match.py
git commit -m "feat: add semantic job ranking with OpenAI fallback"
```

---

### Task 6: URL verification

**Files:**
- Create: `url_verify.py`
- Create: `tests/test_url_verify.py`

**Interfaces:**
- Produces:
  - `verify_job_url(url: str, cache: dict[str, bool] | None = None) -> bool`
  - `apply_url_verification(ranked_jobs: list[RankedJob], cache: dict[str, bool] | None = None) -> list[RankedJob]`
    - Sets `url_verified`; re-sorts verified first, then by `semantic_score`

- [ ] **Step 1: Write failing tests**

Create `tests/test_url_verify.py`:

```python
from unittest.mock import patch

from models import Job, RankedJob
from url_verify import apply_url_verification, verify_job_url


@patch("url_verify.httpx.head")
def test_verify_job_url_ok(mock_head):
    mock_head.return_value.status_code = 200
    assert verify_job_url("https://example.com/job") is True


@patch("url_verify.httpx.head")
def test_verify_job_url_fail(mock_head):
    mock_head.return_value.status_code = 404
    assert verify_job_url("https://example.com/missing") is False


def test_apply_url_verification_reorders():
    job_ok = Job(
        job_title="OK",
        company_name="A",
        job_location="Tokyo",
        job_posting_url="https://ok.example/job",
        job_summary="x",
    )
    job_bad = Job(
        job_title="BAD",
        company_name="B",
        job_location="Tokyo",
        job_posting_url="https://bad.example/job",
        job_summary="y",
    )
    ranked = [
        RankedJob(job=job_bad, match_score=5, reason="b", semantic_score=0.9, url_verified=None),
        RankedJob(job=job_ok, match_score=4, reason="a", semantic_score=0.8, url_verified=None),
    ]

    def fake_verify(url, cache=None):
        return "ok.example" in url

    with patch("url_verify.verify_job_url", side_effect=fake_verify):
        result = apply_url_verification(ranked)
    assert result[0].job.job_title == "OK"
    assert result[0].url_verified is True
    assert result[1].url_verified is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_url_verify.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `url_verify.py`**

```python
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_url_verify.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add url_verify.py tests/test_url_verify.py
git commit -m "feat: verify job posting URLs and reorder rankings"
```

---

### Task 7: gBizINFO client and company fact-check

**Files:**
- Create: `gbiz_client.py`
- Create: `company_factcheck.py`
- Create: `tests/test_gbiz_client.py`
- Create: `tests/test_company_factcheck.py`

**Interfaces:**
- Produces:
  - `search_corporation(name: str) -> dict | None` — best match or None
  - `build_factcheck(company_name: str, job_url: str) -> CompanyFactcheck`

- [ ] **Step 1: Write failing gBiz client test**

Create `tests/test_gbiz_client.py`:

```python
from unittest.mock import patch

from gbiz_client import search_corporation


@patch("gbiz_client.httpx.get")
def test_search_corporation_parses_first_hit(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "hojin-infos": [
            {"corporate_number": "1234567890123", "name": "Example KK", "location": "Tokyo"}
        ]
    }
    result = search_corporation("Example KK")
    assert result["corporate_number"] == "1234567890123"
```

- [ ] **Step 2: Write failing fact-check test**

Create `tests/test_company_factcheck.py`:

```python
from unittest.mock import patch

from company_factcheck import build_factcheck


@patch("company_factcheck.generate_korean_text", return_value="공공 데이터상 정상 법인")
@patch("company_factcheck.search_corporation")
def test_build_factcheck_verified(mock_search, _mock_gemini):
    mock_search.return_value = {
        "corporate_number": "1234567890123",
        "name": "Example KK",
        "location": "Tokyo",
    }
    fc = build_factcheck("Example KK", "https://example.com/job")
    assert fc.status == "verified"
    assert fc.corporate_number == "1234567890123"
    assert "공공" in fc.summary_ko


@patch("company_factcheck.generate_korean_text", return_value="공공 DB 미확인")
@patch("company_factcheck.search_corporation", return_value=None)
def test_build_factcheck_unconfirmed(_mock_search, _mock_gemini):
    fc = build_factcheck("Unknown Co", "https://example.com/job")
    assert fc.status == "public_unconfirmed"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_gbiz_client.py tests/test_company_factcheck.py -v`
Expected: FAIL

- [ ] **Step 4: Implement `gbiz_client.py`**

```python
import os

import httpx


GBIZ_SEARCH_URL = "https://info.gbiz.go.jp/hojin/v1/hojin"


def search_corporation(name: str) -> dict | None:
    token = os.environ.get("GBIZINFO_API_TOKEN")
    if not token:
        return None
    response = httpx.get(
        GBIZ_SEARCH_URL,
        params={"name": name, "limit": 1},
        headers={"X-hojinInfo-api-token": token},
        timeout=15.0,
    )
    if response.status_code != 200:
        return None
    payload = response.json()
    infos = payload.get("hojin-infos") or payload.get("hojin_infos") or []
    if not infos:
        return None
    return infos[0]
```

> **Note:** Confirm exact gBizINFO V2 endpoint and header names against official docs during implementation; adjust URL/keys if API differs.

- [ ] **Step 5: Implement `company_factcheck.py`**

```python
from models import CompanyFactcheck
from gbiz_client import search_corporation
from ai_provider import AiProviderError, generate_korean_text


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
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_gbiz_client.py tests/test_company_factcheck.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add gbiz_client.py company_factcheck.py tests/test_gbiz_client.py tests/test_company_factcheck.py
git commit -m "feat: add gBizINFO lookup and company fact-check builder"
```

---

### Task 8: MVP crew runner and main.py guard

**Files:**
- Create: `crew_runner.py`
- Modify: `main.py`
- Create: `tests/test_crew_runner.py`

**Interfaces:**
- Produces:
  - `run_mvp(resume_text: str, level: str, position: str, location: str = "Japan") -> MvpRunResult`
- Consumes: Crew job search output (`JobList`), `rank_jobs_semantic`, `apply_url_verification`, `build_factcheck`

- [ ] **Step 1: Write failing runner unit test (mock Crew)**

Create `tests/test_crew_runner.py`:

```python
from unittest.mock import MagicMock, patch

from models import Job
from crew_runner import select_best_job


def test_select_best_job_prefers_verified_and_semantic():
    from models import RankedJob

    jobs = [
        RankedJob(
            job=Job(
                job_title="Low",
                company_name="A",
                job_location="Tokyo",
                job_posting_url="https://a.example",
                job_summary="x",
            ),
            match_score=3,
            reason="a",
            semantic_score=0.5,
            url_verified=False,
        ),
        RankedJob(
            job=Job(
                job_title="High",
                company_name="B",
                job_location="Tokyo",
                job_posting_url="https://b.example",
                job_summary="y",
            ),
            match_score=5,
            reason="b",
            semantic_score=0.9,
            url_verified=True,
        ),
    ]
    chosen = select_best_job(jobs)
    assert chosen.job.job_title == "High"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_crew_runner.py -v`
Expected: FAIL

- [ ] **Step 3: Implement selection helper + runner**

Create `crew_runner.py`:

```python
import tempfile
from pathlib import Path

from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource

from company_factcheck import build_factcheck
from main import JobHunterCrew
from models import ChosenJob, JobList, MvpRunResult, RankedJob
from semantic_match import rank_jobs_semantic
from url_verify import apply_url_verification


def select_best_job(ranked_jobs: list[RankedJob]) -> ChosenJob:
    if not ranked_jobs:
        raise ValueError("매칭된 공고가 없습니다.")
    best = ranked_jobs[0]
    return ChosenJob(job=best.job, selected=True, reason=best.reason)


def _run_job_search(resume_text: str, level: str, position: str, location: str) -> JobList:
    with tempfile.TemporaryDirectory() as tmp:
        resume_path = Path(tmp) / "resume.txt"
        resume_path.write_text(resume_text, encoding="utf-8")
        knowledge = TextFileKnowledgeSource(file_paths=[str(resume_path)])
        crew_base = JobHunterCrew()
        search_agent = crew_base.job_search_agent()
        search_agent.knowledge_sources = [knowledge]
        extraction = crew_base.job_extraction_task()
        crew = crew_base.crew()
        crew.tasks = [extraction]
        crew.agents = [search_agent]
        result = crew.kickoff(inputs={"level": level, "position": position, "location": location})
        if isinstance(result, JobList):
            return result
        if hasattr(result, "pydantic"):
            return result.pydantic
        return JobList.model_validate(result)


def run_mvp(
    resume_text: str,
    level: str,
    position: str,
    location: str = "Japan",
) -> MvpRunResult:
    job_list = _run_job_search(resume_text, level, position, location)
    if not job_list.jobs:
        raise ValueError("조건에 맞는 공고를 찾지 못했습니다. 검색 조건을 완화해 보세요.")

    ranked, used_fallback = rank_jobs_semantic(resume_text, job_list.jobs)
    url_cache: dict[str, bool] = {}
    ranked = apply_url_verification(ranked, cache=url_cache)
    chosen = select_best_job(ranked)
    factcheck = build_factcheck(chosen.job.company_name, chosen.job.job_posting_url)

    return MvpRunResult(
        ranked_jobs=ranked,
        chosen_job=chosen,
        factcheck=factcheck,
        used_fallback=used_fallback,
    )
```

Modify `main.py` — wrap kickoff:

```python
if __name__ == "__main__":
    JobHunterCrew().crew().kickoff(
        inputs={
            "level": "Senior",
            "position": "AI Agents Developer",
            "location": "Japan",
        }
    )
```

Remove module-level auto-kickoff at lines 116–122.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_crew_runner.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add crew_runner.py main.py tests/test_crew_runner.py
git commit -m "feat: add MVP crew runner and guard CLI entrypoint"
```

---

### Task 9: Streamlit app

**Files:**
- Create: `app.py`
- Create: `output/.gitkeep` (optional; `output/` already gitignored)

**Interfaces:**
- Consumes: `run_mvp`, `TEMPLATE_PATH`, `parse_resume_bytes`
- Produces: UI with template download, upload, results table, fact-check panel, markdown download

- [ ] **Step 1: Create `app.py`**

```python
import streamlit as st

from company_factcheck import build_factcheck  # noqa: F401 — used indirectly via runner
from crew_runner import run_mvp
from resume_ingest import TEMPLATE_PATH, UnsupportedResumeFormatError, parse_resume_bytes


st.set_page_config(page_title="일본 취업 매칭", layout="wide")
st.title("일본 취업 — 의미 매칭 & 기업 팩트체크")

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

col1, col2, col3 = st.columns(3)
with col1:
    level = st.text_input("레벨", value="Senior")
with col2:
    position = st.text_input("포지션", value="Backend Engineer")
with col3:
    location = st.text_input("근무지", value="Japan")

run = st.button("매칭 실행", type="primary")

if run:
    if uploaded is None:
        st.error("이력서 파일을 업로드해 주세요. 템플릿을 다운로드해 작성할 수 있습니다.")
        st.stop()
    try:
        resume_text = parse_resume_bytes(uploaded.getvalue(), uploaded.name)
    except (UnsupportedResumeFormatError, ValueError) as exc:
        st.error(f"이력서를 읽을 수 없습니다: {exc}")
        st.stop()

    with st.spinner("일본 공고 검색 및 매칭 중..."):
        try:
            result = run_mvp(resume_text, level, position, location)
        except ValueError as exc:
            st.warning(str(exc))
            st.stop()

    if result.used_fallback:
        st.warning("품질↓ OpenAI 장애로 기본 매칭으로 전환되었습니다.")

    rows = []
    for r in result.ranked_jobs:
        rows.append(
            {
                "회사": r.job.company_name,
                "직무": r.job.job_title,
                "semantic_score": r.semantic_score,
                "url_verified": r.url_verified,
                "이유": r.reason,
                "링크": r.job.job_posting_url,
            }
        )
    st.subheader("매칭 결과")
    st.dataframe(rows, use_container_width=True)

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
```

- [ ] **Step 2: Manual smoke test**

Run: `uv run streamlit run app.py`
Expected:
- Template download button works
- Upload `.txt` resume → run → table + fact-check panel (requires live API keys)

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add Streamlit MVP UI for resume upload and results"
```

---

### Task 10: README and acceptance verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add Streamlit + OpenAI + gBizINFO setup section to README**

Include:

```bash
# Run Streamlit MVP (Phase 1 — OpenAI only)
uv run streamlit run app.py
```

Document gBizINFO token application link: https://info.gbiz.go.jp/hojin/portal/top

Phase 2 section: GCP auth + Vertex setup (deferred).

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: all unit tests PASS

- [ ] **Step 3: Acceptance checklist (manual)**

- [ ] Template download → fill → upload → one Streamlit run completes
- [ ] Ranking shows `semantic_score`, Korean `reason`, `url_verified`
- [ ] Selected company shows `verified` or `public_unconfirmed`
- [ ] OpenAI failure path shows "품질↓" badge (simulate by unsetting `OPENAI_API_KEY`)
- [ ] Uploaded file not written to `knowledge/resume.txt`

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document Streamlit MVP setup and acceptance steps"
```

---

## Spec Coverage Self-Review

| Spec requirement | Task |
|------------------|------|
| E semantic match (OpenAI embeddings) | Task 4, 5 |
| C company fact-check (gBizINFO + OpenAI) | Task 7 |
| Streamlit + template download + upload | Task 3, 9 |
| Korean UI output | Task 5, 7, 9 |
| `semantic_score`, `url_verified` fields | Task 2, 5, 6 |
| `CompanyFactcheck` model | Task 2, 7 |
| URL Grounding/verification | Task 6 |
| OpenAI fallback + "품질↓" badge | Task 5, 9 |
| Session-scoped resume (no default persist) | Task 9 (parse in memory only) |
| CLI `main.py` preserved | Task 8 |
| README OpenAI/gBiz/Streamlit docs | Task 10 |
| Vertex / GCP integration | Phase 2 (deferred) |
| Hello Work NOT in MVP | Global Constraints |
| Vector Search deferred | Out of scope |
| Fact-check ChosenJob only | Task 8, 9 |

## Open Items Resolved in This Plan

- Embedding model: `text-embedding-3-small` (OpenAI primary)
- Fact-check scope: `ChosenJob` only
- Template: `.md` only for MVP
- gBizINFO endpoint: verify against official V2 docs during Task 7 (adjust if needed)

## Risks During Implementation

- CrewAI kickoff return type may differ by version — normalize in `_run_job_search` as shown
- gBizINFO API field names may differ — add defensive parsing in `search_corporation`
- Korean resume vs Japanese JD embedding mismatch — if scores cluster low, add JD one-line Korean summary pre-pass in Task 5 follow-up commit
