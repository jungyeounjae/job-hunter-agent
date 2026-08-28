# Korea→Japan Job Hunter MVP Design

**Date:** 2026-08-25  
**Status:** Approved for implementation planning  
**Project:** job-hunter-agent  
**日本語版:** [2026-08-25-korea-japan-semantic-match-factcheck-design.ja.md](./2026-08-25-korea-japan-semantic-match-factcheck-design.ja.md)

## 1. Goal

한국에서 일본 취업을 준비하는 구직자를 위해, 기존 CrewAI 파이프라인에 다음을 추가한다.

- **E — Semantic match:** OpenAI embeddings로 이력서↔일본 공고 의미 매칭
- **C — Company fact-check:** gBizINFO·法人番号 등 공공 데이터 + OpenAI 요약(한국어)

차별점: Geekly / リクルートエージェント의 비공개 구인·인간 협상과 경쟁하지 않고, **근거 있는 매칭**과 **검증 가능한 기업 정보**를 구직자 소유 산출물로 제공한다.

## 2. Target users

- Primary: 일본 취업을 원하는 **한국 구직자**
- Personas (공통 코어로 지원; 페르소나별 심화는 후속): 경력·일본어 상/하, 신입·워홀·유학 전환
- MVP UI language: **한국어**
- Job market focus: **Japan**

## 3. Approach (locked)

**Hybrid:** CrewAI orchestration + **OpenAI primary (Phase 1)** + public corporate APIs + Streamlit UI. **Vertex AI is Phase 2** — not required to ship or accept the MVP.

**AI provider strategy:**

| Phase | Provider | Role |
|-------|----------|------|
| **Phase 1 (MVP)** | **OpenAI** (primary) | `text-embedding-3-small` + `gpt-4o-mini` — semantic match + Korean summaries |
| **Phase 2** | **Vertex AI** (optional) | Vector Search, Grounding, GCP privacy/compliance path; `text-embedding-005` + `gemini-2.0-flash-001` |

- **Phase 1 facade:** `ai_provider.py` exposes `embed_texts()` / `generate_korean_text()` backed by **OpenAI only**; services never call the OpenAI SDK directly
- **Phase 1 fallback:** OpenAI failure → CrewAI LLM keyword matching; UI shows “품질↓” if degraded
- **Phase 2 extension:** `ai_provider` adds Vertex routing (`AI_PROVIDER=vertex`), cross-provider fallback, and Streamlit provider selector — for GCP learning and scale features

Rejected for MVP (Phase 1):

- Pure CLI-only (no UI) — user requested Streamlit upload
- Vertex/Gemini as **required** MVP dependency — deferred to Phase 2
- Hello Work API as primary source — eligibility restricted (see §6)

## 4. Architecture

```
[Streamlit app]
  ├─ Download Korean 직무이력서 template
  ├─ Upload resume (PDF / DOCX / TXT / MD)
  ├─ 「이력서 분석」→ level/position auto-fill (user override)
  ├─ Search inputs: level, position, location(=Japan)
  └─ Run
        │
        ▼
[resume_ingest] → session temp text
        │
        ▼
[resume_analyze] ← ai_provider structured JSON → ResumeProfile
        │
        ▼
[job_search_agent] ← profile search_queries + Firecrawl (MVP public web)
        │
        ▼
[semantic_match] ← matching_document + JD blurb (ko) + ai_provider + URL verify (httpx)
        │
        ▼
[job_selection] → ChosenJob
        │
        ▼
[company_factcheck] ← gBizINFO + ai_provider summary (ko)
        │
        ▼
[Streamlit] profile panel + ranked jobs + company_factcheck.md (+ download)
```

**Boundaries**

| Layer | Responsibility |
|-------|----------------|
| Streamlit | Template download, upload, inputs, results (provider selector: Phase 2) |
| CrewAI | Task order, context, file outputs |
| `ai_provider` | Phase 1: OpenAI embeddings + chat; Phase 2: add Vertex routing |
| OpenAI | `text-embedding-3-small`, `gpt-4o-mini` — **Phase 1 primary** |
| Vertex AI | Vector Search, Grounding, optional provider — **Phase 2** |
| Public APIs | Corporate facts (gBizINFO); URL liveness via HTTP |

**Out of MVP**

- Vector Search managed index (Phase 2)
- 求人ボックス publisher API (after approval)
- ハローワーク API (after occupational referral eligibility)
- Japanese 履歴書/職務経歴書 conversion, visa diagnosis, multimodal portfolio (Phase 3)
- Full SaaS auth/DB

## 5. Data flow and I/O

### 5.1 Run inputs

- Resume text from uploaded file (via `resume_ingest`)
- `{level, position, location}` with default `location=Japan`
- Output language: Korean (`ko`)

### 5.2 Schema changes (minimal)

**`RankedJob` (extend)**

- `semantic_score: float` — primary ranking signal
- `url_verified: bool` — posting URL checked via HTTP HEAD/GET
- Keep existing `match_score` (1–5) as secondary / fallback explanation

**`CompanyFactcheck` (new)**

- `corporate_number: str | None`
- `gbiz_fields: dict` — available public fields
- `risk_tags: list[str]`
- `summary_ko: str`
- `sources: list[str]`
- `status: "verified" | "public_unconfirmed" | "error"`

### 5.3 Outputs

- Streamlit MVP path runs only: search → semantic match → selection → company fact-check
- Streamlit: ranked table + fact-check panel
- Files (optional download): `output/company_factcheck.md`
- Existing resume rewrite / company research / interview prep agents stay in the codebase and remain available via CLI (`main.py`); not required for Streamlit MVP acceptance
- Ranking rule: sort by `semantic_score`; demote/exclude failed `url_verified`

### 5.4 Fallbacks

| Failure | Behavior |
|---------|----------|
| Resume parse failure | Show error; prompt template re-download |
| OpenAI failure (Phase 1) | CrewAI LLM matching; UI badge “품질↓” |
| AI provider failure (Phase 2) | Try alternate provider if configured; else CrewAI LLM; UI badge “품질↓” |
| URL verification failure | Exclude or rank last |
| gBizINFO no match | `public_unconfirmed` + OpenAI summary from job URL context only (no invented facts) |
| Zero jobs from search | Stop; suggest relaxing filters |

## 6. Job data sources (tiered)

| Tier | Source | When |
|------|--------|------|
| MVP | Public web via Firecrawl (ToS/robots respectful) | Now |
| Optional MVP | Wantedly public JSON if terms allow | After legal/ToS check |
| After partnership | 求人ボックス 求人検索API (publisher program; site review; click-out model — not a raw dump) | Post-approval |
| After eligibility | ハローワーク 求人情報提供 API | Only if operator is eligible (e.g. licensed referral business / municipality / school). **Not** free for arbitrary individuals/startups |

Do **not** document Hello Work as “anyone can use free JSON API.”

## 7. Components

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `app.py` (Streamlit) | Template DL, upload, run, display | crew runner |
| `resume_ingest` | PDF/DOCX/TXT/MD → text; template path | pypdf / python-docx (or equivalent) |
| `resume_analyze` | `raw_text` → `ResumeProfile` (structured extraction) | `ai_provider` |
| `job_blurb` | JD → Korean 1–2 sentence blurb for embedding | `ai_provider` |
| `knowledge/templates/직무이력서_템플릿.*` | Downloadable Korean career-history template | — |
| `job_search_agent` | Collect/normalize JP jobs | Firecrawl |
| `ai_provider` | Route embed + chat (Phase 1: OpenAI; Phase 2: +Vertex) | `openai_client` (+ `vertex_client` in Phase 2) |
| `openai_client` | OpenAI embeddings + chat | `openai` SDK |
| `vertex_client` | Vertex embeddings + Gemini | `google-cloud-aiplatform` — **Phase 2** |
| `semantic_match` | Embed + rank + Korean reasons + URL check | `ai_provider` |
| `job_selection` | Pick best job | — |
| `company_factcheck` | Corporate number + gBizINFO + Korean risk summary | Public APIs, `ai_provider` |
| Config / secrets | `OPENAI_API_KEY`, gBizINFO token; GCP vars Phase 2 | `.env` |

`uv run python main.py` remains available for debug without UI.

## 8. Streamlit UX (MVP)

1. Hero/actions: **직무이력서 템플릿 다운로드**
2. File uploader for completed resume
3. Form: level, position, location (default Japan)
4. Run button → progress / logs (lightweight)
5. Results:
   - Fallback badge “품질↓” if OpenAI degraded to CrewAI LLM matching
   - *(Phase 2: sidebar AI provider selector + OpenAI/Vertex badge)*
   - Ranked jobs: title, company, semantic_score, reason_ko, url_verified, link
   - Selected job fact-check: status, risk tags, summary_ko, sources
6. Download fact-check markdown

Template format: Korean **직무이력서** (not Japanese official forms in MVP).

## 9. Security and privacy

- Phase 1: resume/job text sent to **OpenAI** only. Review OpenAI data policy; use org settings to opt out of training where available.
- Phase 2: optional Vertex path for users who prefer GCP private infrastructure — review Google Cloud data processing terms.
- Default: upload and extracted text are **session-scoped temp**; delete after run/session end.
- Keep `output/` and personal resumes gitignored.
- Never log full resume or contact details.
- No API keys in UI or committed files.

## 10. AI providers

| Capability | Phase 1 (OpenAI primary) | Phase 2 (Vertex) |
|------------|--------------------------|------------------|
| Embeddings | `text-embedding-3-small` | `text-embedding-005` |
| Korean reasons / fact-check | `gpt-4o-mini` | `gemini-2.0-flash-001` |
| HTTP URL verify | Yes (httpx) | Yes |
| Vector Search index | — | Managed index for large job corpus |
| Grounding (Google Search) | — | Optional fact-check enrichment |
| Provider switch in UI | — | `AI_PROVIDER=openai\|vertex` + sidebar |

Phase 1 env: `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL`, `OPENAI_CHAT_MODEL` only. GCP / `AI_PROVIDER` vars added in Phase 2.

## 11. Acceptance criteria

1. User can download template, fill, upload, and complete one run from Streamlit.
2. Ranking shows `semantic_score`, Korean `reason`, and `url_verified`.
3. Selected company yields fact-check with corporate public data **or** explicit `public_unconfirmed`.
4. OpenAI failure triggers CrewAI LLM fallback with visible “품질↓” badge.
5. Default config does not persist uploaded resume on disk after session/run cleanup.
6. README documents OpenAI setup, gBizINFO, and Streamlit run command (Vertex/GCP documented as Phase 2).

## 12. Implementation phases

**Phase 1 (this MVP)**  
Streamlit + template + ingest + `ai_provider` (**OpenAI primary**) + semantic_match + company_factcheck + Korean outputs.

**Phase 2**  
Vertex AI integration (`vertex_client`, provider switch, Vector Search, Grounding); 求人ボックス publisher if approved; richer job corpus.

**Phase 3**  
Japanese document conversion, visa heuristics, multimodal inputs.

**Phase 4 (eligibility-gated)**  
ハローワーク API if legally operable.

## 13. Risks

- Job scraping ToS / blocking — mitigate with rate limits, cite sources, prefer partner APIs when available.
- gBizINFO name matching ambiguity (similar company names) — require human-visible candidates or corporate number confirmation when unsure.
- Embedding language mismatch (Korean resume vs Japanese JD) — consider bilingual embedding strategy or translate JD summary before embed; validate in implementation plan.
- Grounding cost/latency — Phase 2 item; Phase 1 uses HTTP URL checks cached per run.

## 14. Open decisions for implementation plan (non-blocking)

- Exact embedding model ID and similarity threshold defaults
- Whether non-selected ranked jobs also get lightweight fact-check or only `ChosenJob`
- Template file format preference: `.md` vs `.docx` (default: ship `.md` for MVP; add `.docx` if upload/parse path already depends on python-docx)
