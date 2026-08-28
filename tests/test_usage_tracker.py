from usage_tracker import (
    record_usage,
    reset_usage_records,
    usage_snapshot,
    usage_totals,
)


class _Usage:
    prompt_tokens = 10
    completion_tokens = 5
    total_tokens = 15


def test_record_usage_and_totals():
    reset_usage_records()
    record_usage("chat", "gpt-4o-mini", _Usage())
    record_usage("embeddings", "text-embedding-3-small", _Usage())
    snapshot = usage_snapshot()
    totals = usage_totals()
    assert len(snapshot) == 2
    assert totals.total_tokens == 30
    assert totals.call_count == 2


def test_reset_usage_records():
    reset_usage_records()
    record_usage("chat", "gpt-4o-mini", _Usage())
    reset_usage_records()
    assert usage_snapshot() == []
    assert usage_totals().call_count == 0
