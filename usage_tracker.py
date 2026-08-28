"""Accumulate OpenAI token usage across a single run."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class UsageRecord:
    operation: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class UsageTotals:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    call_count: int = 0


_records: list[UsageRecord] = []


def reset_usage_records() -> None:
    _records.clear()


def record_usage(operation: str, model: str, usage) -> None:
    if usage is None:
        return
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    total = int(getattr(usage, "total_tokens", 0) or 0)
    if total == 0 and (prompt or completion):
        total = prompt + completion
    _records.append(
        UsageRecord(
            operation=operation,
            model=model,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
        )
    )


def usage_snapshot() -> list[dict]:
    return [asdict(record) for record in _records]


def usage_totals() -> UsageTotals:
    totals = UsageTotals()
    for record in _records:
        totals.prompt_tokens += record.prompt_tokens
        totals.completion_tokens += record.completion_tokens
        totals.total_tokens += record.total_tokens
        totals.call_count += 1
    return totals
