from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from .settings import MIN_MARGIN


@dataclass(frozen=True)
class MatchResult:
    person_id: str | None
    score: float
    second_score: float
    status: str


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("Embeddings must be non-empty and have the same dimension")
    left_norm_sq = math.fsum(float(value) ** 2 for value in left)
    right_norm_sq = math.fsum(float(value) ** 2 for value in right)
    if left_norm_sq == 0.0 or right_norm_sq == 0.0:
        raise ValueError("Zero-length embeddings cannot be compared")
    dot = math.fsum(float(a) * float(b) for a, b in zip(left, right))
    return dot / math.sqrt(left_norm_sq * right_norm_sq)


class IdentityMatcher:
    def __init__(self, threshold: float, min_margin: float = MIN_MARGIN) -> None:
        if not math.isfinite(threshold):
            raise ValueError("threshold must be finite; calibrate it on validation data")
        if not math.isfinite(min_margin) or min_margin < 0.0:
            raise ValueError("min_margin must be a finite non-negative value")
        self.threshold = float(threshold)
        self.min_margin = float(min_margin)

    def match(
        self,
        query_embedding: Sequence[float],
        gallery: Mapping[str, Sequence[Sequence[float]]],
    ) -> MatchResult:
        scored: list[tuple[float, str]] = []
        for person_id, templates in gallery.items():
            if not templates:
                continue
            best_score = max(cosine_similarity(query_embedding, item) for item in templates)
            scored.append((best_score, person_id))
        if not scored:
            return MatchResult(None, 0.0, 0.0, "unknown")

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        best_score, best_id = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else -1.0
        if best_score < self.threshold:
            return MatchResult(None, best_score, second_score, "unknown")
        if len(scored) > 1 and best_score - second_score < self.min_margin:
            return MatchResult(None, best_score, second_score, "ambiguous")
        return MatchResult(best_id, best_score, second_score, "identified")
