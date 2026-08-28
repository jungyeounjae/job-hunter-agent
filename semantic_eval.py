"""Semantic match evaluation against a hand-labeled job set."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from models import Job, LabeledJob, ResumeProfile
from semantic_match import rank_jobs_semantic

DEFAULT_EVAL_DIR = Path("tests/fixtures/eval")


@dataclass
class EvalMetrics:
    job_count: int
    match_count: int
    no_match_count: int
    mean_score_match: float
    mean_score_no_match: float
    score_separation: float
    precision_at_5: float
    precision_at_10: float

    def to_dict(self) -> dict:
        return {
            "job_count": self.job_count,
            "match_count": self.match_count,
            "no_match_count": self.no_match_count,
            "mean_score_match": round(self.mean_score_match, 4),
            "mean_score_no_match": round(self.mean_score_no_match, 4),
            "score_separation": round(self.score_separation, 4),
            "precision_at_5": round(self.precision_at_5, 4),
            "precision_at_10": round(self.precision_at_10, 4),
        }


def load_resume_text(eval_dir: Path = DEFAULT_EVAL_DIR) -> str:
    return (eval_dir / "resume_text.txt").read_text(encoding="utf-8").strip()


def load_resume_profile(eval_dir: Path = DEFAULT_EVAL_DIR) -> ResumeProfile:
    data = json.loads((eval_dir / "resume_profile.json").read_text(encoding="utf-8"))
    return ResumeProfile.model_validate(data)


def load_labeled_jobs(eval_dir: Path = DEFAULT_EVAL_DIR) -> list[LabeledJob]:
    payload = json.loads((eval_dir / "labeled_jobs.json").read_text(encoding="utf-8"))
    return [
        LabeledJob(
            id=item["id"],
            label=item["label"],
            rationale_ko=item.get("rationale_ko", ""),
            job=Job.model_validate(item["job"]),
        )
        for item in payload["jobs"]
    ]


def compute_metrics(
    ranked: list[tuple[str, str, float | None]],
) -> EvalMetrics:
    """ranked: list of (job_id, label, semantic_score) in rank order."""
    by_label: dict[str, list[float]] = {"match": [], "no_match": []}
    for _job_id, label, score in ranked:
        if score is not None:
            by_label[label].append(score)

    def precision_at(k: int) -> float:
        top = ranked[:k]
        if not top:
            return 0.0
        hits = sum(1 for _id, label, _ in top if label == "match")
        return hits / len(top)

    mean_match = sum(by_label["match"]) / len(by_label["match"]) if by_label["match"] else 0.0
    mean_no = (
        sum(by_label["no_match"]) / len(by_label["no_match"]) if by_label["no_match"] else 0.0
    )

    return EvalMetrics(
        job_count=len(ranked),
        match_count=len(by_label["match"]),
        no_match_count=len(by_label["no_match"]),
        mean_score_match=mean_match,
        mean_score_no_match=mean_no,
        score_separation=mean_match - mean_no,
        precision_at_5=precision_at(5),
        precision_at_10=precision_at(10),
    )


def run_eval(
    eval_dir: Path = DEFAULT_EVAL_DIR,
    use_profile: bool = True,
) -> tuple[EvalMetrics, list[tuple[str, str, float | None]]]:
    labeled = load_labeled_jobs(eval_dir)
    resume_text = load_resume_text(eval_dir)
    profile = load_resume_profile(eval_dir) if use_profile else None
    jobs = [item.job for item in labeled]
    id_by_url = {item.job.job_posting_url: item.id for item in labeled}
    label_by_url = {item.job.job_posting_url: item.label for item in labeled}

    ranked_jobs, _used_fallback, _used_raw = rank_jobs_semantic(
        resume_text, jobs, profile=profile
    )

    ranked: list[tuple[str, str, float | None]] = []
    for row in ranked_jobs:
        url = row.job.job_posting_url
        ranked.append((id_by_url[url], label_by_url[url], row.semantic_score))

    return compute_metrics(ranked), ranked


def main() -> None:
    import dotenv

    dotenv.load_dotenv()
    metrics, ranked = run_eval()
    print("=== Semantic Match Eval ===")
    print(json.dumps(metrics.to_dict(), ensure_ascii=False, indent=2))
    print("\n--- Ranked ---")
    for job_id, label, score in ranked:
        print(f"{job_id}\t{label}\t{score}")


if __name__ == "__main__":
    main()
