# Korea→Japan Job Hunter MVP Design

**Date:** 2026-08-25  
**Status:** Approved for implementation planning  
**Project:** job-hunter-agent  
**日本語版:** [2026-08-25-korea-japan-semantic-match-factcheck-design.ja.md](./2026-08-25-korea-japan-semantic-match-factcheck-design.ja.md)

## 1. Goal

한국에서 일본 취업을 준비하는 구직자를 위해, 기존 CrewAI 파이프라인에 다음을 추가한다.

- **E — Semantic match:** Vertex embeddings로 이력서↔일본 공고 의미 매칭
- **C — Company fact-check:** gBizINFO·法人番号 등 공공 데이터 + Grounding으로 기업 신뢰 리포트

차별점: Geekly / リクルートエージェント의 비공개 구인·인간 협상과 경쟁하지 않고, **근거 있는 매칭**과 **검증 가능한 기업 정보**를 구직자 소유 산출물로 제공한다.

## 2. Target users

- Primary: 일본 취업을 원하는 **한국 구직자**
- Personas (공통 코어로 지원; 페르소나별 심화는 후속): 경력·일본어 상/하, 신입·워홀·유학 전환
- MVP UI language: **한국어**
- Job market focus: **Japan**

## 3. Approach (locked)

**Hybrid:** CrewAI orchestration + Vertex AI (embeddings, Gemini, Grounding) + public corporate APIs + Streamlit UI.

Rejected for MVP:

- Pure CLI-only (no UI) — user requested Streamlit upload
- Vertex-only rewrite dropping CrewAI — higher risk, delays E/C validation
- Hello Work API as primary source — eligibility restricted (see §6)

## 4. Architecture

```
[Streamlit app]
  ├─ Download Korean 직무이력서 template
  ├─ Upload resume (PDF / DOCX / TXT / MD)
  ├─ Search inputs: level, position, location(=Japan)
  └─ Run
        │
        ▼
[resume_ingest] → session temp text
        │
        ▼
[job_search_agent] ← Firecrawl (MVP public web)
        │
        ▼
[semantic_match] ← Vertex embeddings + Gemini reason_ko + URL Grounding
        │
        ▼
[job_selection] → ChosenJob
        │
        ▼
[company_factcheck] ← 法人番号 / gBizINFO + Gemini + Grounding
        │
        ▼
[Streamlit] ranked jobs + company_factcheck.md (+ download)
```

**Boundaries**

| Layer | Responsibility |
|-------|----------------|
| Streamlit | Template download, upload, inputs, results |
| CrewAI | Task order, context, file outputs |
| Vertex | Embeddings, Gemini explanations/reports, Grounding |
| Public APIs | Corporate facts (not job corpus in MVP) |

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
- `url_verified: bool` — posting URL checked via Grounding/fetch
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
| Vertex embedding/Gemini failure | Fall back to existing LLM matching; UI badge “품질↓” |
| URL verification failure | Exclude or rank last |
| gBizINFO no match | `public_unconfirmed` + weaker web-Grounding-only report |
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
| `knowledge/templates/직무이력서_템플릿.*` | Downloadable Korean career-history template | — |
| `job_search_agent` | Collect/normalize JP jobs | Firecrawl |
| `semantic_match` | Embed + rank + Korean reasons + URL check | Vertex AI |
| `job_selection` | Pick best job | — |
| `company_factcheck` | Corporate number + gBizINFO + Korean risk summary | Public APIs, Vertex |
| Config / secrets | GCP project, API keys | `.env` / Secret Manager |

`uv run python main.py` remains available for debug without UI.

## 8. Streamlit UX (MVP)

1. Hero/actions: **직무이력서 템플릿 다운로드**
2. File uploader for completed resume
3. Form: level, position, location (default Japan)
4. Run button → progress / logs (lightweight)
5. Results:
   - Ranked jobs: title, company, semantic_score, reason_ko, url_verified, link
   - Selected job fact-check: status, risk tags, summary_ko, sources
6. Download fact-check markdown

Template format: Korean **직무이력서** (not Japanese official forms in MVP).

## 9. Security and privacy

- Resume content sent to models only via **Vertex AI** path (enterprise data governance; customer data not used to train foundation models per GCP terms — lock project settings accordingly).
- Default: upload and extracted text are **session-scoped temp**; delete after run/session end.
- Keep `output/` and personal resumes gitignored.
- Never log full resume or contact details.
- No API keys in UI or committed files.

## 10. Vertex usage (MVP vs later)

| Capability | MVP | Later |
|------------|-----|-------|
| text-embedding + in-batch cosine | Yes | — |
| Gemini Korean reasons / fact-check | Yes | — |
| Grounding (URL / company claims) | Yes | — |
| Vector Search index | No | Phase 2 when corpus grows |
| Multimodal PDF/portfolio in one shot | No | Phase 3 |
| Vertex vs AI Studio | Vertex (GCP) for quotas/privacy | — |

## 11. Acceptance criteria

1. User can download template, fill, upload, and complete one run from Streamlit.
2. Ranking shows `semantic_score`, Korean `reason`, and `url_verified`.
3. Selected company yields fact-check with corporate public data **or** explicit `public_unconfirmed`.
4. Vertex outage triggers LLM fallback with visible quality badge.
5. Default config does not persist uploaded resume on disk after session/run cleanup.
6. README documents GCP/Vertex setup, gBizINFO access, and Streamlit run command.

## 12. Implementation phases

**Phase 1 (this MVP)**  
Streamlit + template + ingest + semantic_match + company_factcheck + Grounding + Korean outputs.

**Phase 2**  
Vector Search; 求人ボックス publisher if approved; richer job corpus.

**Phase 3**  
Japanese document conversion, visa heuristics, multimodal inputs.

**Phase 4 (eligibility-gated)**  
ハローワーク API if legally operable.

## 13. Risks

- Job scraping ToS / blocking — mitigate with rate limits, cite sources, prefer partner APIs when available.
- gBizINFO name matching ambiguity (similar company names) — require human-visible candidates or corporate number confirmation when unsure.
- Embedding language mismatch (Korean resume vs Japanese JD) — consider bilingual embedding strategy or translate JD summary before embed; validate in implementation plan.
- Grounding cost/latency — cache URL checks per run.

## 14. Open decisions for implementation plan (non-blocking)

- Exact embedding model ID and similarity threshold defaults
- Whether non-selected ranked jobs also get lightweight fact-check or only `ChosenJob`
- Template file format preference: `.md` vs `.docx` (default: ship `.md` for MVP; add `.docx` if upload/parse path already depends on python-docx)
