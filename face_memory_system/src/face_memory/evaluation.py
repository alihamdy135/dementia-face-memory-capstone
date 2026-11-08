from __future__ import annotations

import csv
from pathlib import Path
import time
from typing import Protocol, Sequence

from .core import IdentityMatcher
from .metrics import evaluate_open_set, latency_summary, select_threshold
from .opencv_backend import FaceEncoderError
from .settings import MIN_MARGIN, MODEL_VERSION


class Encoder(Protocol):
    def encode_image(self, image_path: str | Path) -> Sequence[float]: ...


def _load_manifest(manifest_path: str | Path) -> tuple[list[dict[str, str]], Path]:
    path = Path(manifest_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Manifest not found: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"image_path", "person_id", "split", "session_id"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("Manifest must contain image_path, person_id, split, and session_id columns")
        rows = list(reader)
    if not rows:
        raise ValueError("Manifest contains no image records")

    allowed_splits = {"gallery", "validation", "test"}
    seen_paths: set[str] = set()
    session_splits: dict[str, set[str]] = {}
    for row in rows:
        row["image_path"] = row["image_path"].strip()
        row["person_id"] = row["person_id"].strip()
        row["split"] = row["split"].strip().lower()
        if not row["image_path"] or not row["person_id"]:
            raise ValueError("Each manifest row needs image_path and person_id")
        if not row.get("session_id", "").strip():
            raise ValueError("Each image must include a non-empty capture session_id")
        if row["split"] not in allowed_splits:
            raise ValueError(f"Invalid split {row['split']!r}; expected gallery, validation, or test")
        image_path = Path(row["image_path"])
        if not image_path.is_absolute():
            image_path = path.parent / image_path
        image_path = image_path.resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"Image listed in manifest does not exist: {image_path}")
        row["resolved_path"] = str(image_path)
        if str(image_path) in seen_paths:
            raise ValueError(f"The same image appears more than once in the manifest: {image_path}")
        seen_paths.add(str(image_path))
        session_id = row.get("session_id", "").strip()
        session_splits.setdefault(session_id, set()).add(row["split"])
    leaked_sessions = [session for session, splits in session_splits.items() if len(splits) > 1]
    if leaked_sessions:
        raise ValueError(
            "A capture session appears in multiple splits; keep each complete session in one split"
        )
    if not any(row["split"] == "gallery" for row in rows):
        raise ValueError("Manifest must contain at least one gallery image")

    validation_unknown = {
        row["person_id"] for row in rows if row["split"] == "validation"
    }
    test_unknown = {row["person_id"] for row in rows if row["split"] == "test"}
    gallery_ids = {row["person_id"] for row in rows if row["split"] == "gallery"}
    validation_unknown -= gallery_ids
    test_unknown -= gallery_ids
    if validation_unknown & test_unknown:
        raise ValueError("Unknown identities must be disjoint between validation and test")
    return rows, path.parent


def evaluate_manifest(
    manifest_path: str | Path,
    encoder: Encoder,
    split: str,
    threshold: float | None = None,
    max_unknown_fpir: float | None = None,
    min_margin: float = MIN_MARGIN,
    camera: str = "not recorded",
    device: str = "not recorded",
) -> dict[str, object]:
    split = split.lower()
    if split not in {"validation", "test"}:
        raise ValueError("Evaluation split must be validation or test")
    if (threshold is None) == (max_unknown_fpir is None):
        raise ValueError("Provide exactly one of threshold or max_unknown_fpir")
    if max_unknown_fpir is not None and split != "validation":
        raise ValueError("Threshold calibration is allowed only on the validation split")

    rows, _ = _load_manifest(manifest_path)
    gallery_rows = [row for row in rows if row["split"] == "gallery"]
    gallery: dict[str, list[list[float]]] = {}
    for row in gallery_rows:
        embedding = encoder.encode_image(row["resolved_path"])
        gallery.setdefault(row["person_id"], []).append([float(value) for value in embedding])

    queries = [row for row in rows if row["split"] == split]
    if not queries:
        raise ValueError(f"Manifest has no {split} queries")
    gallery_ids = set(gallery)
    true_ids: list[str | None] = []
    candidate_ids: list[str | None] = []
    scores: list[float] = []
    margins: list[float] = []
    latencies: list[float] = []
    detection_failures = 0
    prediction_rows: list[dict[str, object]] = []
    candidate_matcher = IdentityMatcher(threshold=-1.0, min_margin=0.0)

    for row in queries:
        actual_id = row["person_id"] if row["person_id"] in gallery_ids else None
        started = time.perf_counter()
        try:
            embedding = encoder.encode_image(row["resolved_path"])
            match = candidate_matcher.match(embedding, gallery)
            candidate_id = match.person_id
            score = match.score
            margin = match.score - match.second_score
        except FaceEncoderError:
            detection_failures += 1
            candidate_id = None
            score = -1.0
            margin = 0.0
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        true_ids.append(actual_id)
        candidate_ids.append(candidate_id)
        scores.append(score)
        margins.append(margin)
        latencies.append(elapsed_ms)
        prediction_rows.append(
            {
                "image_path": row["resolved_path"],
                "true_person_id": actual_id,
                "candidate_person_id": candidate_id,
                "best_cosine_similarity": score,
                "best_second_margin": margin,
                "face_detection_or_encoding_failure": candidate_id is None and score == -1.0,
            }
        )

    selected_threshold: float | None = None
    if max_unknown_fpir is not None:
        selected_threshold = select_threshold(
            true_ids,
            candidate_ids,
            scores,
            max_unknown_fpir=max_unknown_fpir,
            margins=margins,
            min_margin=min_margin,
        )
        threshold = selected_threshold
    assert threshold is not None
    report = evaluate_open_set(
        true_ids, candidate_ids, scores, threshold, margins=margins, min_margin=min_margin
    )
    report["split"] = split
    report["gallery_person_count"] = len(gallery)
    report["gallery_template_count"] = len(gallery_rows)
    report["detection_or_encoding_failures"] = detection_failures
    report["detection_or_encoding_failure_rate"] = detection_failures / len(queries)
    report["latency"] = latency_summary(latencies)
    report["model_version"] = MODEL_VERSION
    report["metadata"] = {
        "camera": camera,
        "device": device,
        "known_identities": len(gallery_ids),
        "unknown_identities": len({row["person_id"] for row in queries if row["person_id"] not in gallery_ids}),
        "known_identity_count": sum(identity is not None for identity in true_ids),
        "stranger_query_count": sum(identity is None for identity in true_ids),
    }
    report["predictions"] = prediction_rows
    if selected_threshold is not None:
        report["selected_threshold"] = selected_threshold
        report["validation_constraint_max_unknown_fpir"] = max_unknown_fpir
    report["threshold_curve"] = [
        {
            "threshold": candidate_threshold,
            "known_top1_accuracy": evaluate_open_set(
                true_ids, candidate_ids, scores, candidate_threshold, margins, min_margin
            )["known_top1_accuracy"],
            "unknown_fpir": evaluate_open_set(
                true_ids, candidate_ids, scores, candidate_threshold, margins, min_margin
            )["unknown_fpir"],
        }
        for candidate_threshold in sorted({-1.0, *scores, 1.0000001})
    ]
    return report
