from math import log2
from statistics import median
from typing import Any


def hit_rate_at_k(rows: list[dict[str, Any]], k: int) -> float:
    if not rows:
        return 0.0
    hits = 0
    for row in rows:
        expected = set(row["expected_titles"])
        observed = row["source_titles"][:k]
        if not expected:
            hits += int(row.get("insufficient_evidence") or not observed)
        else:
            hits += int(bool(expected & set(observed)))
    return hits / len(rows)


def mrr(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    total = 0.0
    for row in rows:
        expected = set(row["expected_titles"])
        if not expected:
            total += 1.0 if row.get("insufficient_evidence") or not row["source_titles"] else 0.0
            continue
        for index, title in enumerate(row["source_titles"], start=1):
            if title in expected:
                total += 1.0 / index
                break
    return total / len(rows)


def ndcg_at_k(rows: list[dict[str, Any]], k: int) -> float:
    if not rows:
        return 0.0
    total = 0.0
    for row in rows:
        expected = set(row["expected_titles"])
        if not expected:
            total += 1.0 if row.get("insufficient_evidence") or not row["source_titles"][:k] else 0.0
            continue
        dcg = 0.0
        for index, title in enumerate(row["source_titles"][:k], start=1):
            if title in expected:
                dcg += 1.0 / log2(index + 1)
        ideal = sum(1.0 / log2(index + 1) for index in range(1, min(len(expected), k) + 1))
        total += dcg / ideal if ideal else 0.0
    return total / len(rows)


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return float(ordered[index])


def summarize_latencies(stage_rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    by_stage: dict[str, list[float]] = {}
    for row in stage_rows:
        by_stage.setdefault(row["name"], []).append(float(row.get("duration_ms") or 0.0))
    return {
        name: {
            "p50_ms": round(median(values), 2),
            "p95_ms": round(percentile(values, 0.95), 2),
        }
        for name, values in by_stage.items()
    }
