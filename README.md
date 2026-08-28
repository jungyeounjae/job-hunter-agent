# job-hunter-agent

韓国から日本就職を目指す求職者向けに、求人検索・意味的マッチング・企業ファクトチェックを支援するマルチエージェントプロジェクトです。

**CrewAI CLI** と **Streamlit MVP**（OpenAI 意味マッチ + gBizINFO 企業検証）が利用できます。**Vertex AI は Phase 2** で統合予定です。

| 言語 | 設計書 |
|------|--------|
| 原文 | [docs/superpowers/specs/2026-08-25-korea-japan-semantic-match-factcheck-design.md](docs/superpowers/specs/2026-08-25-korea-japan-semantic-match-factcheck-design.md) |
| 日本語 | [docs/superpowers/specs/2026-08-25-korea-japan-semantic-match-factcheck-design.ja.md](docs/superpowers/specs/2026-08-25-korea-japan-semantic-match-factcheck-design.ja.md) |
| 実装プラン | [docs/superpowers/plans/2026-08-28-korea-japan-mvp-implementation.md](docs/superpowers/plans/2026-08-28-korea-japan-mvp-implementation.md) |
| Resume Intelligence 設計 | [docs/superpowers/specs/2026-08-28-resume-intelligence-design.md](docs/superpowers/specs/2026-08-28-resume-intelligence-design.md) |

## プロダクト方針（MVP）

- **ターゲット:** 日本就職を希望する韓国の求職者（UI 出力は韓国語）
- **E — Semantic match:** OpenAI embeddings で履歴書↔日本求人を意味的にランキング
- **R — Resume intelligence:** AI が非標準履歴書を構造化 (`ResumeProfile`) し、検索・マッチングに反映
- **C — Company fact-check:** 法人番号 / gBizINFO + OpenAI 要約（韓国語）
- **AI プロバイダ:** Phase 1 は **OpenAI のみ**（契約済み）。**Vertex AI** は Phase 2（Vector Search、Grounding、GCP 学習用）
- **UI:** Streamlit（職務履歴書テンプレ DL + ファイルアップロード）
- **差別化:** 非公開求人や年収交渉の代行ではなく、根拠付きマッチングと検証可能な企業情報

求人ソースは段階導入です（MVP は公開 Web / Firecrawl。求人ボックス・ハローワークは提携・利用資格後）。詳細は設計書 §6 を参照してください。

## セットアップ

```bash
uv sync --extra dev
cp .env.example .env
cp knowledge/resume.txt.example knowledge/resume.txt   # CLI 用。自分の履歴書に書き換え
```

`.env` に少なくとも次を設定します。

| 変数 | 用途 |
|------|------|
| `OPENAI_API_KEY` | CLI / MVP AI（embeddings + chat） |
| `SERPER_API_KEY` | 検索連携（環境により使用） |
| `FIRECRAWL_API_KEY` | Web 検索・求人ページ取得 |
| `OPENAI_EMBEDDING_MODEL` | 既定 `text-embedding-3-small` |
| `OPENAI_CHAT_MODEL` | 既定 `gpt-4o-mini` |
| `GBIZINFO_API_TOKEN` | 法人ファクトチェック（[gBizINFO ポータル](https://info.gbiz.go.jp/hojin/portal/top) で申請） |

### Phase 2 で追加予定（Vertex AI）

| 変数 | 用途 |
|------|------|
| `AI_PROVIDER` | `openai` または `vertex` |
| `GOOGLE_CLOUD_PROJECT` | Vertex 使用時 |
| `GOOGLE_CLOUD_LOCATION` | 例: `asia-northeast1` |
| `VERTEX_EMBEDDING_MODEL` | 例: `text-embedding-005` |
| `VERTEX_GEMINI_MODEL` | 例: `gemini-2.0-flash-001` |

**Vertex セットアップ（Phase 2）:**

```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=your-project-id
export AI_PROVIDER=vertex
```

## 実行

### Streamlit MVP（推奨）

```bash
uv run streamlit run app.py
```

フロー: 職務履歴書テンプレート DL → 記入 → アップロード → **「이력서 분석」** → level/position 自動入力（編集可）→ **「매칭 실행」** → マッチング結果 + 企業ファクトチェック表示。

**R → E → C パイプライン:**

| 段階 | 名前 | 役割 |
|------|------|------|
| **R** | Resume intelligence | AI が履歴書を構造化 (`ResumeProfile`) |
| **E** | Semantic match | プロフィール基盤の求人検索 + 意味的ランキング（JD 韓国語 blurb 含む） |
| **C** | Company fact-check | gBizINFO による企業検証 |

**semantic_score 目安:** 0.5+ 良好 · 0.35–0.5 普通 · 0.35 未満 弱い（相対順位も参照）

### CLI（フルパイプライン）

```bash
uv run python main.py
```

検索条件は `main.py` 末尾の `inputs` で変更できます。

### テスト

```bash
uv run pytest -v
```

### 意味マッチ評価セット（手動ラベル 18件）

本職務経歴書ベースの `match` 9件 / `no_match` 9件。プロンプトや blurb 変更の回帰判定用。

```bash
# オフライン（フィクスチャ・メトリクス検証）
uv run pytest tests/test_semantic_eval.py -v

# OpenAI 実 API でスコア分離を確認
uv run pytest -m live tests/test_semantic_eval.py -v

# レポート出力
uv run python semantic_eval.py
```

フィクスチャ: `tests/fixtures/eval/`（`resume_text.txt`, `resume_profile.json`, `labeled_jobs.json`）

## エージェントの流れ

### 現行 CLI（実装済み）

実行するとエージェントが **順番に** 連携します。

| 順番 | エージェント | 役割 |
|------|-------------|------|
| 1 | **Job Search** | Web 検索（Firecrawl）で条件に合う求人を収集・リスト化 |
| 2 | **Job Matching** | `knowledge/resume.txt` と求人を照合し、適合度 1〜5 点と理由を付与 |
| 3 | **Job Matching** | スコア・理由に基づき **最も適した求人 1 件** を選定 |
| 4 | **Resume Optimization** | 選定求人に合わせて履歴書を書き直し（事実の捏造なし） |
| 5 | **Company Research** | 選定企業・チーム・プロダクト・想定面接テーマを Web で調査 |
| 6 | **Interview Prep** | 上記を統合し、面接準備ブリーフィングを作成 |

> 2〜3 は同じ `job_matching_agent` が連続タスクで実行します。

### Streamlit MVP パス（実装済み）

| 順番 | ステップ | 役割 |
|------|----------|------|
| 1 | Resume ingest | アップロード履歴書をテキスト化（セッション一時） |
| 2 | **Resume analyze (R)** | AI が `ResumeProfile` を生成、level/position 自動入力 |
| 3 | Job Search | プロフィール検索クエリ + 公開求人の収集 |
| 4 | Semantic match (E) | `matching_document` + JD 韓国語 blurb で OpenAI 意味マッチ + URL 検証 |
| 5 | Job selection | 最適 1 件を選定 |
| 6 | Company fact-check (C) | gBizINFO + OpenAI レポート（韓国語） |

履歴書書き換え・面接準備エージェントは CLI に残し、Streamlit MVP の必須受け入れ条件には含めません。

## 成果物

### 現行 CLI（`output/`）

| ファイル | 内容 |
|----------|------|
| `rewritten_resume.md` | 選定求人向けに最適化した履歴書 |
| `company_research.md` | 企業概要、ミッション、ニュース、想定面接テーマ、逆質問 |
| `interview_prep.md` | 求人サマリー、フィット理由、想定質問・戦略アドバイス |

### Streamlit MVP

| ファイル | 内容 |
|----------|------|
| `company_factcheck.md` | 公共データに基づく企業ファクトチェック（韓国語、UI から DL） |

`output/` と個人の履歴書ファイルは `.gitignore` され、GitHub にはアップロードされません。

## ロードマップ（要約）

| Phase | 内容 |
|-------|------|
| **1（MVP）** | Streamlit、`ai_provider`（**OpenAI プライマリ**）、**R** resume intelligence、semantic match、fact-check |
| **2** | Vertex AI 統合、Vector Search、求人ボックス（承認後）、求人コーパス拡充 |
| **3** | 日本の履歴書/職務経歴書変換、ビザ、マルチモーダル |
| **4** | 利用資格がある場合のハローワーク API |

## ライセンス・注意

- 求人の取得は各サイトの利用規約・robots を尊重してください。
- ハローワーク求人情報提供 API は職業紹介事業者・自治体等に利用が限られます。個人開発で「誰でも無料 API」と誤解しないでください。
