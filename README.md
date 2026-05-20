# job-hunter-agent

CrewAI による求人検索・マッチング・応募準備を自動化するマルチエージェントプロジェクトです。

## セットアップ

```bash
uv sync
cp .env.example .env
cp knowledge/resume.txt.example knowledge/resume.txt   # 自分の履歴書に書き換え
```

`.env` に `OPENAI_API_KEY`、`SERPER_API_KEY`、`FIRECRAWL_API_KEY` を設定してください。

## 実行

```bash
uv run python main.py
```

検索条件は `main.py` 末尾の `inputs` で変更できます（例: レベル `Senior`、ポジション `AI Agents Developer`、勤務地 `Japan`）。

## エージェントの流れ

実行すると 5 つのエージェントが **順番に** 連携して動きます。

| 順番 | エージェント | 役割 |
|------|-------------|------|
| 1 | **Job Search** | ウェブ検索（Serper）で条件に合う求人を収集・リスト化 |
| 2 | **Job Matching** | `knowledge/resume.txt` と求人を照合し、適合度 1〜5 点と理由を付与 |
| 3 | **Job Matching** | スコア・理由に基づき **最も適した求人 1 件** を選定 |
| 4 | **Resume Optimization** | 選定求人に合わせて履歴書を書き直し（事実の捏造なし） |
| 5 | **Company Research** | 選定企業・チーム・プロダクト・想定面接テーマをウェブで調査 |
| 6 | **Interview Prep** | 上記の結果を統合し、面接準備ブリーフィングを作成 |

> 2〜3 は同じ `job_matching_agent` が連続タスクで実行します。  
> 4〜6 は選定された求人を基準に進み、面接準備は履歴書・企業調査の結果を参照します。

## 成果物（`output/`）

| ファイル | 内容 |
|----------|------|
| `rewritten_resume.md` | 選定求人向けに最適化した履歴書 |
| `company_research.md` | 企業概要、ミッション、ニュース、想定面接テーマ、逆質問リスト |
| `interview_prep.md` | 求人サマリー、フィット理由、履歴書ハイライト、想定質問・戦略アドバイス |

`output/` と `knowledge/resume.txt` は `.gitignore` され、GitHub にはアップロードされません。
