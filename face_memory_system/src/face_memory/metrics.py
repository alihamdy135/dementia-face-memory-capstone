from __future__ import annotations

import math
from typing import Sequence


UNKNOWN = None


def _validate_inputs(
    true_ids: Sequence[str | None],
    candidate_ids: Sequence[str | None],
    scores: Sequence[float],
) -> None:
    if not (len(true_ids) == len(candidate_ids) == len(scores)):
        raise ValueError("true_ids, candidate_ids, and scores must have equal lengths")
    if not true_ids:
        raise ValueError("At least one evaluation query is required")
    if any(not math.isfinite(float(score)) for score in scores):
        raise ValueError("All similarity scores must be finite")


def _accepted_predictions(
    candidate_ids: Sequence[str | None],
    scores: Sequence[float],
    threshold: float,
    margins: Sequence[float] | None = None,
    min_margin: float = 0.0,
) -> list[str | None]:
    if not math.isfinite(threshold):
        raise ValueError("threshold must be finite")
    if not math.isfinite(min_margin) or min_margin < 0:
        raise ValueError("min_margin must be finite and non-negative")
    if margins is not None and len(margins) != len(scores):
        raise ValueError("margins and scores must have equal lengths")
    return [
        candidate
        if score >= threshold and (margins is None or margins[index] >= min_margin)
        else None
        for index, (candidate, score) in enumerate(zip(candidate_ids, scores))
    ]


def _class_scores(
    true_ids: Sequence[str | None], predicted_ids: Sequence[str | None]
) -> tuple[dict[str, dict[str, float | int]], dict[str, dict[str, int]]]:
    labels = sorted({"<unknown>" if item is None else item for item in true_ids + predicted_ids})
    confusion = {actual: {predicted: 0 for predicted in labels} for actual in labels}
    for actual, predicted in zip(true_ids, predicted_ids):
        actual_label = "<unknown>" if actual is None else actual
        predicted_label = "<unknown>" if predicted is None else predicted
        confusion[actual_label][predicted_label] += 1

    report: dict[str, dict[str, float | int]] = {}
    for label in labels:
        true_positive = confusion[label][label]
        false_positive = sum(confusion[actual][label] for actual in labels if actual != label)
        false_negative = sum(confusion[label][predicted] for predicted in labels if predicted != label)
        support = sum(confusion[label].values())
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        report[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
    return report, confusion


def evaluate_open_set(
    true_ids: Sequence[str | None],
    candidate_ids: Sequence[str | None],
    scores: Sequence[float],
    threshold: float,
    margins: Sequence[float] | None = None,
    min_margin: float = 0.0,
) -> dict[str, object]:
    _validate_inputs(true_ids, candidate_ids, scores)
    predicted_ids = _accepted_predictions(candidate_ids, scores, threshold, margins, min_margin)
    total = len(true_ids)
    known_indices = [index for index, identity in enumerate(true_ids) if identity is not None]
    unknown_indices = [index for index, identity in enumerate(true_ids) if identity is None]
    if not known_indices or not unknown_indices:
        raise ValueError("Open-set evaluation requires both known and unknown queries")

    correct = sum(actual == predicted for actual, predicted in zip(true_ids, predicted_ids))
    known_correct = sum(true_ids[index] == predicted_ids[index] for index in known_indices)
    known_accepted = sum(predicted_ids[index] is not None for index in known_indices)
    unknown_accepted = sum(predicted_ids[index] is not None for index in unknown_indices)
    accepted = sum(predicted is not None for predicted in predicted_ids)
    class_report, confusion = _class_scores(true_ids, predicted_ids)
    class_count = len(class_report)

    return {
        "threshold": threshold,
        "min_margin": min_margin,
        "query_count": total,
        "known_query_count": len(known_indices),
        "unknown_query_count": len(unknown_indices),
        "overall_accuracy": correct / total,
        "known_top1_accuracy": known_correct / len(known_indices),
        "known_identification_failure_rate": (len(known_indices) - known_correct) / len(known_indices),
        "known_wrong_identity_rate": (known_accepted - known_correct) / len(known_indices),
        "known_acceptance_rate": known_accepted / len(known_indices),
        "known_false_rejection_rate": (len(known_indices) - known_accepted) / len(known_indices),
        "unknown_fpir": unknown_accepted / len(unknown_indices),
        "unknown_rejection_recall": (len(unknown_indices) - unknown_accepted) / len(unknown_indices),
        "coverage": accepted / total,
        "accepted_identity_precision": known_correct / accepted if accepted else 0.0,
        "macro_precision": sum(item["precision"] for item in class_report.values()) / class_count,
        "macro_recall": sum(item["recall"] for item in class_report.values()) / class_count,
        "macro_f1": sum(item["f1"] for item in class_report.values()) / class_count,
        "per_class": class_report,
        "confusion_matrix": confusion,
    }


def select_threshold(
    true_ids: Sequence[str | None],
    candidate_ids: Sequence[str | None],
    scores: Sequence[float],
    max_unknown_fpir: float,
    margins: Sequence[float] | None = None,
    min_margin: float = 0.0,
) -> float:
    _validate_inputs(true_ids, candidate_ids, scores)
    if not math.isfinite(max_unknown_fpir) or not 0.0 <= max_unknown_fpir <= 1.0:
        raise ValueError("max_unknown_fpir must be between 0 and 1")
    if not any(identity is not None for identity in true_ids):
        raise ValueError("Threshold calibration requires known validation queries")
    if not any(identity is None for identity in true_ids):
        raise ValueError("Threshold calibration requires identity-disjoint unknown validation queries")

    candidates = sorted({float(score) for score in scores})
    candidates.append(math.nextafter(max(candidates), math.inf))
    eligible: list[tuple[int, float, float, float]] = []
    for threshold in candidates:
        predictions = _accepted_predictions(candidate_ids, scores, threshold, margins, min_margin)
        unknown_indices = [i for i, identity in enumerate(true_ids) if identity is None]
        known_indices = [i for i, identity in enumerate(true_ids) if identity is not None]
        unknown_fpir = sum(predictions[i] is not None for i in unknown_indices) / len(unknown_indices)
        if unknown_fpir > max_unknown_fpir:
            continue
        correct_known = sum(true_ids[i] == predictions[i] for i in known_indices)
        eligible.append((correct_known, -unknown_fpir, threshold))
    if not eligible:
        raise RuntimeError("No threshold satisfies the requested validation FPIR")
    return max(eligible)[2]


def latency_summary(latencies_ms: Sequence[float]) -> dict[str, float | int]:
    if not latencies_ms:
        raise ValueError("At least one latency measurement is required")
    values = sorted(float(value) for value in latencies_ms)
    if any(not math.isfinite(value) or value < 0.0 for value in values):
        raise ValueError("Latency values must be finite and non-negative")
    p95_index = max(0, math.ceil(0.95 * len(values)) - 1)
    return {
        "count": len(values),
        "mean_ms": sum(values) / len(values),
        "median_ms": (values[(len(values) - 1) // 2] + values[len(values) // 2]) / 2.0,
        "p95_ms": values[p95_index],
        "max_ms": values[-1],
    }
