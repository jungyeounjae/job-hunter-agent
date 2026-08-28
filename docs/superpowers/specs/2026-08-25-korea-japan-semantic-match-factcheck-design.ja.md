# Korea→Japan Job Hunter MVP 設計書

**日付:** 2026-08-25  
**ステータス:** 実装計画の作成承認済み  
**プロジェクト:** job-hunter-agent  
**原文:** [2026-08-25-korea-japan-semantic-match-factcheck-design.md](./2026-08-25-korea-japan-semantic-match-factcheck-design.md)

## 1. 目的

韓国から日本就職を目指す求職者向けに、既存の CrewAI パイプラインへ次を追加する。

- **E — Semantic match:** OpenAI embeddings により職務経歴書↔日本の求人を意味的にマッチング
- **C — Company fact-check:** gBizINFO・法人番号などの公共データ + OpenAI 要約（韓国語）

差別化: Geekly / リクルートエージェントの非公開求人・人間による交渉と正面衝突せず、**根拠のあるマッチング**と**検証可能な企業情報**を求職者自身の成果物として提供する。

## 2. ターゲットユーザー

- Primary: 日本就職を希望する **韓国の求職者**
- ペルソナ（共通コアで対応。ペルソナ別の深掘りは後続）: 経験者・日本語上/下、新卒・ワーホリ・留学からの就職転換
- MVP UI 言語: **韓国語**
- 求人市場の焦点: **Japan**

## 3. アプローチ（確定）

**ハイブリッド:** CrewAI オーケストレーション + **OpenAI プライマリ（Phase 1）** + 公共法人 API + Streamlit UI。**Vertex AI は Phase 2** — MVP の出荷・受け入れには不要。

**AI プロバイダ戦略:**

| Phase | プロバイダ | 役割 |
|-------|-----------|------|
| **Phase 1（MVP）** | **OpenAI**（プライマリ） | `text-embedding-3-small` + `gpt-4o-mini` — 意味マッチ + 韓国語要約 |
| **Phase 2** | **Vertex AI**（任意） | Vector Search、Grounding、GCP プライバシー/コンプライアンス経路 |

- **Phase 1 ファサード:** `ai_provider.py` が `embed_texts()` / `generate_korean_text()` を提供（**OpenAI のみ**）
- **Phase 1 フォールバック:** OpenAI 障害 → CrewAI LLM マッチング。UI に「品質↓」
- **Phase 2 拡張:** `ai_provider` に Vertex ルーティング（`AI_PROVIDER=vertex`）、クロスプロバイダフォールバック、Streamlit プロバイダ選択を追加

MVP（Phase 1）で採用しないもの:

- UI なしの CLI のみ — Streamlit アップロードを要求済み
- Vertex/Gemini を **MVP 必須依存** にする — Phase 2 に延期
- ハローワーク API を主ソースにする — 利用資格制限あり（§6 参照）

## 4. アーキテクチャ

```
[Streamlit app]
  ├─ 韓国語「職務履歴書」テンプレートのダウンロード
  ├─ 履歴書アップロード（PDF / DOCX / TXT / MD）
  ├─ 検索条件: level, position, location(=Japan)
  └─ 実行
        │
        ▼
[resume_ingest] → セッション一時テキスト
        │
        ▼
[job_search_agent] ← Firecrawl（MVP: 公開 Web）
        │
        ▼
[semantic_match] ← ai_provider (OpenAI) + reason_ko + URL verify (httpx)
        │
        ▼
[job_selection] → ChosenJob
        │
        ▼
[company_factcheck] ← gBizINFO + ai_provider summary (ko)
        │
        ▼
[Streamlit] ランキング求人 + company_factcheck.md（+ ダウンロード）
```

**境界**

| レイヤー | 責任 |
|----------|------|
| Streamlit | テンプレ DL、アップロード、入力、結果（プロバイダ選択: Phase 2） |
| CrewAI | タスク順序、コンテキスト、ファイル出力 |
| `ai_provider` | Phase 1: OpenAI。Phase 2: Vertex ルーティング追加 |
| OpenAI | `text-embedding-3-small`, `gpt-4o-mini` — **Phase 1 プライマリ** |
| Vertex AI | Vector Search、Grounding — **Phase 2** |
| 公共 API | gBizINFO、HTTP URL 確認 |

**MVP 対象外**

- Vector Search マネージドインデックス（Phase 2）
- 求人ボックス publisher API（承認後）
- ハローワーク API（職業紹介等の利用資格取得後）
- 日本の履歴書/職務経歴書変換、ビザ診断、マルチモーダル・ポートフォリオ（Phase 3）
- 本格 SaaS の認証/DB

## 5. データフローと入出力

### 5.1 実行入力

- アップロードファイルから抽出した履歴書テキスト（`resume_ingest` 経由）
- `{level, position, location}`（既定 `location=Japan`）
- 出力言語: 韓国語（`ko`）

### 5.2 スキーマ変更（最小）

**`RankedJob`（拡張）**

- `semantic_score: float` — 主ランキング信号
- `url_verified: bool` — 求人 URL を HTTP HEAD/GET で確認
- 既存の `match_score`（1–5）は副次 / フォールバック説明用として維持

**`CompanyFactcheck`（新規）**

- `corporate_number: str | None`
- `gbiz_fields: dict` — 取得できた公開フィールド
- `risk_tags: list[str]`
- `summary_ko: str`
- `sources: list[str]`
- `status: "verified" | "public_unconfirmed" | "error"`

### 5.3 出力

- Streamlit MVP パスは次のみ実行: 検索 → semantic match → 選定 → 企業ファクトチェック
- Streamlit: ランキング表 + ファクトチェックパネル
- ファイル（任意ダウンロード）: `output/company_factcheck.md`
- 既存の履歴書書き換え / 企業調査 / 面接準備エージェントはコードベースに残し、CLI（`main.py`）で利用可能。Streamlit MVP の受け入れ条件には含めない
- ランキング規則: `semantic_score` でソート。`url_verified` 失敗は降格または除外

### 5.4 フォールバック

| 失敗 | 動作 |
|------|------|
| 履歴書パース失敗 | エラー表示。テンプレ再ダウンロードを促す |
| OpenAI 障害（Phase 1） | CrewAI LLM マッチング。UI「品質↓」 |
| AI プロバイダ障害（Phase 2） | 代替プロバイダ（設定済みなら）→ CrewAI LLM。UI「品質↓」 |
| URL 検証失敗 | 除外または最下位 |
| gBizINFO 未マッチ | `public_unconfirmed` + 提供データのみで OpenAI 要約 |
| 検索 0 件 | 停止。条件緩和を提案 |

## 6. 求人データソース（段階）

| 段階 | ソース | 時期 |
|------|--------|------|
| MVP | Firecrawl 経由の公開 Web（ToS/robots 尊重） | 現在 |
| MVP 任意 | Wantedly 公開 JSON（利用条件確認後） | 法務/ToS 確認後 |
| 提携後 | 求人ボックス 求人検索API（publisher。サイト審査。クリック送客モデル — 生ダンプではない） | 承認後 |
| 資格取得後 | ハローワーク 求人情報提供 API | 利用対象（有料/無料職業紹介事業者、自治体、学校等）に該当する場合のみ。**個人や一般スタートアップが誰でも無料 JSON を使えるわけではない** |

ハローワークを「誰でも無料の JSON API」と記載してはならない。

## 7. コンポーネント

| 単位 | 責任 | 依存 |
|------|------|------|
| `app.py`（Streamlit） | テンプレ DL、アップロード、実行、表示 | crew runner |
| `resume_ingest` | PDF/DOCX/TXT/MD → テキスト。テンプレパス提供 | pypdf / python-docx 等 |
| `knowledge/templates/직무이력서_템플릿.*` | ダウンロード可能な韓国語職務履歴書テンプレ | — |
| `job_search_agent` | 日本求人の収集・正規化 | Firecrawl |
| `ai_provider` | embed + chat ルーティング（Phase 1: OpenAI; Phase 2: +Vertex） | `openai_client`（Phase 2: +`vertex_client`） |
| `openai_client` | OpenAI embeddings + chat | `openai` SDK |
| `vertex_client` | Vertex embeddings + Gemini | `google-cloud-aiplatform` — **Phase 2** |
| `semantic_match` | Embed + ランク + 韓国語理由 + URL 確認 | `ai_provider` |
| `job_selection` | 最適求人 1 件の選定 | — |
| `company_factcheck` | 法人番号 + gBizINFO + 韓国語リスク要約 | 公共 API、`ai_provider` |
| Config / secrets | `OPENAI_API_KEY`、gBizINFO トークン。GCP は Phase 2 | `.env` |

`uv run python main.py` は UI なしのデバッグ用として残す。

## 8. Streamlit UX（MVP）

1. 主要アクション: **職務履歴書テンプレートのダウンロード**
2. 記入済み履歴書のファイルアップローダ
3. フォーム: level, position, location（既定 Japan）
4. 実行ボタン → 進捗 / ログ（軽量）
5. 結果:
   - フォールバック「品質↓」バッジ（OpenAI 障害時）
   - *(Phase 2: サイドバー AI プロバイダ選択 + OpenAI/Vertex バッジ)*
   - ランキング: title, company, semantic_score, reason_ko, url_verified, link
   - 選定企業ファクトチェック: status, risk tags, summary_ko, sources
6. ファクトチェック Markdown ダウンロード

テンプレ形式: 韓国語の **職務履歴書**（MVP では日本の正式な履歴書様式ではない）。

## 9. セキュリティとプライバシー

- Phase 1: 履歴書/求人テキストは **OpenAI** のみに送信。OpenAI データポリシーを確認すること。
- Phase 2: GCP プライベートインフラを希望するユーザー向けに Vertex 経路を追加 — Google Cloud データ処理条項を確認すること。
- 既定: アップロードと抽出テキストは **セッション一時**。実行/セッション終了後に削除。
- `output/` と個人履歴書は gitignore を維持。
- 履歴書全文・連絡先をログに残さない。
- API キーを UI やコミット対象に置かない。

## 10. AI プロバイダ

| 機能 | Phase 1（OpenAI プライマリ） | Phase 2（Vertex） |
|------|------------------------------|-------------------|
| Embeddings | `text-embedding-3-small` | `text-embedding-005` |
| 韓国語理由/ファクトチェック | `gpt-4o-mini` | `gemini-2.0-flash-001` |
| HTTP URL verify | Yes（httpx） | Yes |
| Vector Search インデックス | — | 大規模求人コーパス用 |
| Grounding（Google Search） | — | ファクトチェック強化（任意） |
| UI プロバイダ切替 | — | `AI_PROVIDER=openai\|vertex` + サイドバー |

Phase 1 環境変数: `OPENAI_API_KEY`、`OPENAI_EMBEDDING_MODEL`、`OPENAI_CHAT_MODEL` のみ。GCP / `AI_PROVIDER` は Phase 2 で追加。

## 11. 受け入れ条件

1. Streamlit からテンプレ DL → 記入 → アップロード → 1 サイクル実行ができる
2. ランキングに `semantic_score`、韓国語 `reason`、`url_verified` が表示される
3. 選定企業のファクトチェックが公共法人データ付き、または明示的な `public_unconfirmed` になる
4. OpenAI 障害時に CrewAI LLM フォールバックが動き、UI に「品質↓」バッジが出る
5. 既定設定ではセッション/実行クリーンアップ後にアップロード履歴書がディスクに残らない
6. README に OpenAI 設定、gBizINFO 利用、Streamlit 実行手順が書かれている（Vertex/GCP は Phase 2 として記載）

## 12. 実装フェーズ

**Phase 1（本 MVP）**  
Streamlit + テンプレ + ingest + `ai_provider`（**OpenAI プライマリ**）+ semantic_match + company_factcheck + 韓国語出力。

**Phase 2**  
Vertex AI 統合（`vertex_client`、プロバイダ切替、Vector Search、Grounding）。求人ボックス publisher（承認時）。求人コーパス拡充。

**Phase 3**  
日本書類変換、ビザヒューリスティック、マルチモーダル入力。

**Phase 4（資格依存）**  
法的に運用可能な場合のハローワーク API。

## 13. リスク

- 求人スクレイピングの ToS / ブロック — レート制限、出典明示、提携 API 優先で緩和
- gBizINFO の社名マッチ曖昧性 — 不確かな場合は候補を人間に見せる、または法人番号確認を要求
- 埋め込みの言語不一致（韓国語履歴書 vs 日本語 JD） — バイリンガル埋め込み、または embed 前の JD 要約翻訳を実装計画で検証
- Grounding のコスト/レイテンシ — Phase 2 項目。Phase 1 では HTTP URL チェックを実行単位でキャッシュ

## 14. 実装計画に委ねる未決事項（ブロッカーではない）

- 埋め込みモデル ID と類似度しきい値の既定値
- 非選定のランキング求人にも軽いファクトチェックを付けるか、`ChosenJob` のみか
- テンプレ形式: `.md` vs `.docx`（既定: MVP は `.md`。アップロード解析が python-docx 依存なら `.docx` も追加）
