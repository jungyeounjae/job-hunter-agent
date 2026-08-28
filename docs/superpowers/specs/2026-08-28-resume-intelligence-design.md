# Resume Intelligence Layer Design (R)

**Date:** 2026-08-28  
**Status:** Approved for implementation planning  
**Project:** job-hunter-agent  
**Extends:** [2026-08-25-korea-japan-semantic-match-factcheck-design.md](./2026-08-25-korea-japan-semantic-match-factcheck-design.md)  
**日本語版:** (Phase 1.5 승인 후 작성)

## 1. Problem statement

현재 MVP는 업로드된 이력서를 **평문 추출 → 임베딩**만 수행한다.

| 현재 동작 | 한계 |
|-----------|------|
| `resume_ingest`가 PDF/DOCX → 텍스트 변환 | 형식·섹션 구조 무시 |
| `job_search`는 `level` / `position` / `location`만 사용 | **이력서 내용이 검색에 반영되지 않음** |
| `semantic_match`가 원문 이력서를 임베딩 | 비표준·다국어 이력서에서 점수 0.3대로 하락 |
| LLM은 매칭 **이유 문장** 생성에만 사용 (이력서 앞 2000자) | 구조화·문맥 이해 없음 |

**사용자 인사이트 (locked):** 구직자는 통일되지 않은 다양한 직무이력서를 가진다. AI가 **문맥을 이해하고 구조화**한 뒤, 그 결과로 일본 공고를 **조사·매칭**해야 한다.

## 2. Goal

**R — Resume intelligence:** 업로드 이력서(임의 형식)를 AI가 분석해 **정규화 프로필(`ResumeProfile`)**을 만들고, 이후 **공고 검색(E 전단)**과 **의미 매칭(E)**에 사용한다.

성공 기준:

1. 템플릿·자유 형식·PDF 모두에서 **스킬·경력·희망직무·언어·비자** 등 핵심 필드 추출
2. 추출 결과가 **공고 검색 쿼리**와 **매칭 임베딩 입력**에 반영
3. 분석 실패 시 **기존 raw-text 경로로 폴백** (서비스 중단 없음)
4. UI에서 사용자가 **분석 결과를 확인**할 수 있음 (블랙박스 아님)

**Out of scope (this design):**

- 일본식 履歴書/職務経歴書 자동 변환 (Phase 3)
- 멀티모달(이미지 스캔 PDF OCR 고도화) — 텍스트 추출 실패 시 에러만
- 이력서 DB 영구 저장
- 사용자가 분석 결과를 수동 편집하는 UI (후속)

## 3. Approach options

### Option A — LLM structured extraction only (recommended)

`gpt-4o-mini` + **JSON schema / Pydantic structured output**으로 `ResumeProfile` 1회 생성.

| Pros | Cons |
|------|------|
| 비표준 이력서·한일 혼용에 강함 | 호출 1회 추가 (비용·지연) |
| 구현 단순, 테스트 용이 | 환각 위험 → `null` + `warnings`로 완화 |
| 기존 `ai_provider` 확장으로 일관 | |

### Option B — Heuristic parser + LLM

규칙 기반 섹션 분리 후 LLM이 필드만 채움.

| Pros | Cons |
|------|------|
| 템플릿 이력서에 저렴 | **다양한 형식에 취약** (사용자 요구와 충돌) |
| | 유지보수 부담 (언어·레이아웃별 규칙) |

### Option C — Two-pass (normalize → extract)

1차: 자유 텍스트 → 표준 요약문, 2차: 요약문 → JSON.

| Pros | Cons |
|------|------|
| PDF 깨짐·잡음에 유리 | **2× LLM 비용·지연** |
| | MVP 이후 품질 개선용으로 적합 |

**Decision (locked for Phase 1.5):** **Option A**를 기본으로 채택.  
`parse_warnings`가 많거나 추출 텍스트가 짧을 때만 **Option C의 1차 정규화**를 조건부 실행 (see §5.4).

## 4. Architecture

```
[Streamlit app]
  ├─ Upload resume (any supported format)
  ├─ Optional overrides: level, position, location
  └─ Run
        │
        ▼
[resume_ingest] → raw_text (session only)
        │
        ▼
[resume_analyze] ← ai_provider structured JSON
        │            produces ResumeProfile
        ▼
[job_search_agent] ← profile.search_queries + overrides
        │
        ▼
[semantic_match] ← embed profile.matching_document (not raw resume)
        │            + bilingual job summary prep (optional)
        ▼
[job_selection] → ChosenJob
        │
        ▼
[company_factcheck] (unchanged)
        │
        ▼
[Streamlit] profile panel + ranked jobs + fact-check
```

**Feature letter:** 기존 E(semantic match), C(fact-check)에 **R(resume intelligence)** 추가.  
파이프라인: **R → E → C** (순서 고정).

### R → E → C 파이프라인 설명

| 단계 | 이름 | 입력 | 출력 | 역할 |
|------|------|------|------|------|
| **R** | Resume intelligence | 업로드 파일 | `ResumeProfile` | AI가 비표준 이력서를 **구조화** — 스킬·직무·검색어·매칭용 요약문 생성 |
| **E** | Semantic match (+ search) | `ResumeProfile` + 일본 공고 목록 | `RankedJob[]` | 프로필 기반 **공고 검색** → 후보 공고와 **의미 유사도** 랭킹 |
| **C** | Company fact-check | 선정 1건 공고의 회사명 | `CompanyFactcheck` | gBizINFO **공공 데이터**로 기업 신뢰도 검증 |

**데이터 흐름 (한 줄):**  
`이력서 파일` → **R**이 이해·정리 → **E**가 그 프로필로 일본 공고를 찾고 순위 매김 → **C**가 1위 기업을 팩트체크.

**R이 없을 때 (현재 MVP):** E가 원문 이력서를 그대로 임베딩하고, 검색은 UI의 level/position만 사용 → 점수 0.3대·검색 부정확.

**E 내부 2단계:**
1. **Search** — `ResumeProfile.search_queries_ja`로 Firecrawl/CrewAI가 일본 공고 수집
2. **Match** — `matching_document` ↔ 공고(JD 한국어 blurb 포함) 임베딩 비교 + 한국어 매칭 이유

**C는 R/E 결과에 의존하지 않음** — 선정된 `ChosenJob.company_name`만 사용.

### Boundaries

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `resume_ingest` | bytes → `raw_text` | pypdf, python-docx |
| **`resume_analyze`** | `raw_text` → `ResumeProfile` | `ai_provider` |
| **`ai_provider`** | + `generate_structured()` for Pydantic models | `openai_client` |
| `crew_runner` | orchestrate R→E→C; pass profile to search/match | all above |
| `semantic_match` | embed `matching_document`; rank | `ResumeProfile` |
| `job_search` (Crew task) | use profile-driven queries | `ResumeProfile` |

## 5. Data model

### 5.1 `ResumeProfile` (new)

```python
class ResumeProfile(BaseModel):
    # Core identity (for matching & display)
    headline_ko: str                          # 1문장 후보 요약 (한국어)
    target_roles: list[str]                   # 희망/적합 직무 (한국어 또는 영어)
    seniority_level: str | None               # e.g. Junior, Mid, Senior
    years_of_experience: float | None         # null if unknown
    skills: list[str]                         # 기술·도메인 스킬
    languages: dict[str, str]                 # e.g. {"ko": "native", "ja": "business"}
    visa_status: str | None                   # null if not stated
    preferred_locations: list[str]            # e.g. ["Tokyo", "Japan"]

    # Search drivers (for job_search_agent)
    search_queries_ja: list[str]              # 일본어 검색어 1–3개
    search_queries_en: list[str]               # 영어 검색어 0–2개

    # Matching input (for embeddings — bilingual normalized text)
    matching_document: str                    # 구조화 요약 + 핵심 경력 (≤4000 chars)

    # Quality metadata
    confidence: float                         # 0.0–1.0 overall
    field_confidence: dict[str, float]        # per-field optional
    parse_warnings: list[str]                 # e.g. "비자 정보 없음"
    status: Literal["ok", "partial", "failed"]
```

**Rules:**

- 텍스트에 **없는 사실은 invent 금지** → `null` / 빈 리스트 + `parse_warnings`
- `matching_document`는 **한국어 중심 + 일본 취업 관련 키워드(직무·스킬) 일본어 병기** 권장
- `search_queries_ja`는 Firecrawl/Web search에 직접 사용 (일본 채용 시장용)

### 5.2 `MvpRunResult` (extend)

```python
class MvpRunResult(BaseModel):
    resume_profile: ResumeProfile | None      # None if analyze failed completely
    ranked_jobs: list[RankedJob]
    chosen_job: ChosenJob
    factcheck: CompanyFactcheck
    used_fallback: bool                       # OpenAI degrade OR resume analyze fallback
    used_raw_resume_fallback: bool            # True if matching used raw_text not profile
```

### 5.3 Search inputs merge policy

Crew `kickoff` inputs:

| Field | Source priority |
|-------|-----------------|
| `level` | **분석 후 UI 자동 채움** (`profile.seniority_level`); 사용자가 수정하면 override |
| `position` | **분석 후 UI 자동 채움** (`profile.target_roles[0]`); 사용자가 수정하면 override |
| `location` | UI 값 (default `Japan`) |
| `search_queries` | `profile.search_queries_ja` + `search_queries_en` (new task template var) |

**Locked (2026-08-28):** Streamlit은 이력서 분석 직후 `level` / `position` 필드를 **자동 채움**한다. 사용자는 실행 전·후 언제든 수정 가능. 자동 채움은 `st.session_state`로 관리하며, 수동 수정 시 해당 값이 검색에 우선한다.

## 6. `resume_analyze` behavior

### 6.1 Interface

```python
def analyze_resume(raw_text: str) -> ResumeProfile:
    """LLM structured extraction. Never raises — returns status=failed profile on error."""
```

### 6.2 Prompt strategy

System 역할: 한국→일본 취업 코치 + 이력서 파서.

User content:

- 전체 `raw_text` (max **12,000 chars**; 초과 시 앞 8k + 뒤 4k)
- 출력: `ResumeProfile` JSON schema

Constraints in prompt:

- 근거 없는 비자·경력년수·학력 **추정 금지**
- 불명확 필드는 `null` + `parse_warnings`에 이유
- `matching_document`에 스킬·경력·희망직무·언어를 **문단 형태**로 재구성
- 일본 취업 검색용 `search_queries_ja` 예: `シニア バックエンドエンジニア 東京`

### 6.3 Conditional normalize pass (Option C lite)

Trigger when **any**:

- `len(raw_text.strip()) < 200`
- PDF 추출 후 줄바꿈·공백 비율 이상 (garbled heuristic)
- 1차 `analyze_resume` 결과 `status == "partial"` AND `confidence < 0.5`

Action: `generate_korean_text`로 “이력서 정리본” 1회 생성 → 재분석 1회.  
2회 실패 시 `status=failed`, downstream은 raw_text 폴백.

### 6.4 `ai_provider` extension

```python
def generate_structured[T: BaseModel](prompt: str, model_type: type[T]) -> T:
    """OpenAI chat with response_format / JSON schema → Pydantic parse."""
```

`openai_client`에서 `client.beta.chat.completions.parse` 또는 `response_format: json_schema` 사용.

## 7. Downstream integration

### 7.1 Job search (`crew_runner` + `config/tasks.yaml`)

**`job_extraction_task` description 확장:**

```
Find jobs in {location} for a candidate with:
- Seniority: {level}
- Target role: {position}
- Additional search queries: {search_queries}

Use Web Search Tool with the queries above (prioritize Japanese queries).
Extract jobs matching the candidate profile.
```

`search_queries` = `", ".join(profile.search_queries_ja + profile.search_queries_en)`.

### 7.2 Semantic match (`semantic_match.py`)

**Before (current):**

```python
vectors = embed_texts([resume_text, *documents])
```

**After:**

```python
candidate_doc = profile.matching_document if profile and profile.status != "failed" else resume_text
job_docs = [build_job_document(job, blurb_ko=blurbs[job.job_posting_url]) for job in jobs]
vectors = embed_texts([candidate_doc, *job_docs])
```

**JD 한국어 blurb pre-pass (동일 PR — locked):**  
각 `Job`의 `job_summary`(및 `full_raw_job_description` 있으면 포함)를 OpenAI로 **한국어 1–2문장** 요약 (`job_matching_blurb_ko`). `build_job_document`에 blurb를 넣어 **한국어화된 공고 ↔ `matching_document`** 임베딩 비교.  
- run 단위 blurb **캐시** (동일 URL 중복 호출 방지)  
- blurb 생성 실패 시 원문 `build_job_document`만 사용

**Reason prompt:** `profile.headline_ko`, `profile.skills`를 명시적으로 포함.

### 7.3 RankedJob / scoring

- `semantic_score` 의미 유지 (코사인 유사도)
- **UI에 해석 가이드 추가:** 0.5+ 양호, 0.35–0.5 보통, 0.35 미만 약함 (상대 순위 병행 표시)
- `match_score` (1–5)는 유지; 향후 `profile.confidence`로 가중 가능 (open)

## 8. Streamlit UX

### 8.1 Run flow

1. 업로드 (기존)
2. **[NEW] 분석 단계** 스피너: “이력서 분석 중…”
3. **[NEW] `st.expander('이력서 분석 결과')`** — 분석 성공/부분/실패 배지
   - headline, target_roles, skills, languages, visa, search_queries
   - `parse_warnings` 목록
4. 검색·매칭 스피너 (기존)
5. 결과 테이블 + 팩트체크 (기존)

### 8.2 Badges

| State | UI |
|-------|-----|
| `status=ok` | 🟢 분석 완료 |
| `status=partial` | 🟡 일부 항목 미확인 |
| `status=failed` | 🟠 원문 기반 매칭 (품질↓) |
| `used_fallback` (OpenAI) | 기존 품질↓ 배지 유지 |

### 8.3 Form behavior (locked)

1. 업로드 후 **「이력서 분석」** (또는 Run 시 1단계) → `ResumeProfile` 생성
2. 분석 완료 시 `level` ← `seniority_level`, `position` ← `target_roles[0]` **자동 채움**
3. 사용자가 필드를 수정하면 **수정값이 검색에 사용** (자동 채움 덮어쓰기)
4. `location` 기본값 `Japan` 유지

## 9. Security and privacy

- `raw_text`와 `ResumeProfile` 모두 **세션 스코프**; 디스크 미저장 (기존 정책 유지)
- 로그에 `raw_text` / `matching_document` 전문 금지; `status`, `confidence`, 필드 개수만
- OpenAI structured output에도 동일 데이터 전송 — 기존 Phase 1 정책 준수

## 10. Fallbacks

| Failure | Behavior |
|---------|----------|
| `resume_ingest` 실패 | 에러 표시, 실행 중단 (기존) |
| `analyze_resume` failed | `resume_profile=None`, `used_raw_resume_fallback=True`; raw_text로 E 계속 |
| `analyze_resume` partial | 프로필 사용 + warnings 표시 |
| OpenAI structured parse error | 1회 재시도 → failed 프로필 |
| Job search 0건 | 기존: 조건 완화 안내; **추가:** `search_queries` 완화 제안 |

## 11. Testing strategy

| Layer | Test |
|-------|------|
| `resume_analyze` | Mock LLM: 한국어 자유형 이력서 → skills/roles 추출 |
| | Mock: 비자 미기재 → `visa_status is None` + warning |
| | Mock: LLM 실패 → `status=failed` |
| `generate_structured` | Mock OpenAI parse → Pydantic model |
| `crew_runner` | Profile search_queries가 task inputs에 전달되는지 |
| `semantic_match` | `matching_document` + JD blurb embed 인자 검증 |
| Integration | Fixture 이력서 E2E (live API optional, marked `@pytest.mark.live`) |

**Fixture files:** `tests/fixtures/resumes/` — `template_ko.md`, `freeform_ko.txt`, `minimal.txt`

## 12. Acceptance criteria

1. 자유 형식 한국어 이력서 업로드 시 Streamlit에 **분석 결과 패널** 표시.
2. 분석된 `search_queries_ja`가 job search task에 전달됨 (unit test로 검증).
3. `semantic_match`가 `matching_document` + JD 한국어 blurb를 임베딩에 사용 — profile ok 시.
4. 분석 실패 시에도 파이프라인 완료 + `used_raw_resume_fallback` 배지.
5. 환각 방지: 비자·경력년수 미기재 이력서에서 해당 필드 `null` (테스트 fixture).
6. 기존 18+ 테스트 회귀 없음; 신규 테스트 8+ 추가.

## 13. Implementation scope (single PR)

**Phase 1.5 — one PR, includes:**

| Item | Module |
|------|--------|
| `ResumeProfile` + `MvpRunResult` extend | `models.py` |
| `generate_structured()` | `ai_provider`, `openai_client` |
| `analyze_resume()` | `resume_analyze.py` |
| Profile-driven job search | `crew_runner`, `config/tasks.yaml` |
| `matching_document` + **JD blurb** embedding | `semantic_match.py` (`job_blurb.py` or inline) |
| 분석 패널 + level/position 자동 채움 | `app.py` |

**Deferred:** Vertex analyze path (Phase 2), 일본어 spec `.ja.md` (승인 후)

## 14. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| LLM 환각 (없는 스킬 invent) | prompt 금지 + `parse_warnings`; UI에 “AI 추출” 명시 |
| PDF 텍스트 깨짐 | conditional normalize pass; 사용자에게 DOCX/TXT 권장 |
| 추가 지연 (+3–8s) | 분석 단계 별도 스피너; 향후 session cache |
| 검색 쿼리 품질 | `search_queries_ja`를 UI에 노출해 사용자 검증 가능 |
| UI 기본값이 프로필 덮어씀 | 분석 후 자동 채움 + 사용자 수정 시 override (§5.3, §8.3) |

## 15. Relation to existing MVP spec

- [2026-08-25-korea-japan-semantic-match-factcheck-design.md](./2026-08-25-korea-japan-semantic-match-factcheck-design.md) §4 architecture에 **`[resume_analyze]`** 단계 삽입 (승인 후 해당 문서 PATCH).
- E(semantic match)의 입력이 **raw resume → ResumeProfile.matching_document**로 변경.
- C(fact-check) 변경 없음.

## 16. Locked decisions

| # | Decision | Choice (2026-08-28) |
|---|----------|---------------------|
| 1 | UI level/position | **분석 후 자동 채움** (수정 가능) |
| 2 | `generate_structured` 모델 | `gpt-4o-mini` |
| 3 | JD blurb pre-pass | **동일 PR** (Phase 1.5 단일 배포) |
| 4 | 일본어 spec | 승인 후 `.ja.md` 추가 |

---

**Next step after approval:** `writing-plans` → `docs/superpowers/plans/2026-08-28-resume-intelligence-implementation.md`
