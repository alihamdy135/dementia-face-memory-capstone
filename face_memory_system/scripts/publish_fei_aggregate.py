"""Publish only aggregate FEI benchmark results and anonymized poster figures."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

from face_memory.poster_artifacts import _flow_svg, _threshold_svg


FEI_SOURCE = "https://fei.edu.br/~cet/facedatabase.html"
FEI_TERMS = "FEI permits research use; redistribution or reproduction of the database is not permitted."


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _confusion_svg(test: dict[str, object]) -> str:
    raw_matrix = test["confusion_matrix"]
    assert isinstance(raw_matrix, dict)
    identities = [key for key in raw_matrix if key != "<unknown>"]
    # Randomize the one-run display mapping and never save it alongside the figure.
    random.SystemRandom().shuffle(identities)
    display = {identity: f"ID-{index:03d}" for index, identity in enumerate(identities, 1)}
    display["<unknown>"] = "Unknown"
    order = identities + (["<unknown>"] if "<unknown>" in raw_matrix else [])
    size = len(order)
    cell = 8
    left, top = 190, 145
    plot = size * cell
    width, height = left + plot + 125, top + plot + 110
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Test confusion matrix, anonymous identities</title>',
        '<desc id="desc">Row-normalized confusion matrix with randomly assigned anonymous labels.</desc>',
        f'<rect width="100%" height="100%" fill="#fff"/><text x="{width/2}" y="42" text-anchor="middle" font-family="Arial,sans-serif" font-size="24" font-weight="700" fill="#263b34">Test Confusion Matrix</text>',
        f'<text x="{width/2}" y="70" text-anchor="middle" font-family="Arial,sans-serif" font-size="13" fill="#738178">100 known identities · Unknown · n={test["query_count"]} · anonymous display order</text>',
        f'<text x="{left+plot/2}" y="{height-22}" text-anchor="middle" font-family="Arial,sans-serif" font-size="13" fill="#52645a">Predicted identity</text>',
        f'<text transform="translate(30 {top+plot/2}) rotate(-90)" text-anchor="middle" font-family="Arial,sans-serif" font-size="13" fill="#52645a">Actual identity</text>',
    ]
    for i, actual in enumerate(order):
        row = raw_matrix[actual]
        row_total = sum(int(v) for v in row.values())
        for j, predicted in enumerate(order):
            value = int(row[predicted])
            if not value:
                continue
            fraction = value / row_total if row_total else 0
            color = "#34745e" if actual == predicted else "#cf765b"
            opacity = 0.12 + 0.82 * fraction
            x, y = left + j * cell, top + i * cell
            parts.append(f'<rect x="{x}" y="{y}" width="{cell-1}" height="{cell-1}" fill="{color}" fill-opacity="{opacity:.2}"/>')
    tick_indexes = sorted(set([0, *range(9, len(identities), 10), len(order) - 1]))
    for i in tick_indexes:
        if i < len(order):
            label = "Unknown" if order[i] == "<unknown>" else display[order[i]]
            x = left + i * cell + cell / 2
            y = top + i * cell + cell / 2 + 4
            parts.append(f'<text x="{x}" y="{top-12}" transform="rotate(-55 {x} {top-12})" text-anchor="end" font-family="Arial,sans-serif" font-size="10" fill="#64766b">{label}</text>')
            parts.append(f'<text x="{left-10}" y="{y}" text-anchor="end" font-family="Arial,sans-serif" font-size="10" fill="#64766b">{label}</text>')
    parts.append('</svg>')
    return "".join(parts)


def build(validation: dict[str, object], test: dict[str, object]) -> dict[str, object]:
    vm = validation["metadata"]
    tm = test["metadata"]
    assert isinstance(vm, dict) and isinstance(tm, dict)
    assert validation["split"] == "validation" and test["split"] == "test"
    assert validation["selected_threshold"] == test["threshold"]
    assert vm["dataset_name"] == tm["dataset_name"]
    assert vm["protocol_note"] == tm["protocol_note"]

    known_test = [item for item in test["predictions"] if item["true_person_id"] is not None]
    unknown_test = [item for item in test["predictions"] if item["true_person_id"] is None]
    known_detect_failures = sum(bool(item["face_detection_or_encoding_failure"]) for item in known_test)
    unknown_detect_failures = sum(bool(item["face_detection_or_encoding_failure"]) for item in unknown_test)
    assert len(known_test) == int(test["known_query_count"])
    assert len(unknown_test) == int(test["unknown_query_count"])
    known_errors = round(float(test["known_identification_failure_rate"]) * len(known_test))
    assert known_detect_failures <= known_errors

    protocol = str(tm["protocol_note"])
    known_top1 = float(test["known_top1_accuracy"])
    macro_f1 = float(test["macro_f1"])
    unknown_fpir = float(test["unknown_fpir"])
    threshold = float(test["threshold"])
    val_fp_count = round(float(validation["unknown_fpir"]) * int(validation["unknown_query_count"]))
    val_known_errors = round(float(validation["known_identification_failure_rate"]) * int(validation["known_query_count"]))

    return {
        "status": "measured",
        "dataset": {
            "name": str(tm["dataset_name"]),
            "source": FEI_SOURCE,
            "use_terms": FEI_TERMS,
            "images": 2800,
            "identities": 200,
        },
        "protocol": {
            "split_seed": 20261108,
            "description": protocol,
            "capture_sessions": "Not documented by source; image-level still-image benchmark, no session grouping.",
            "near_duplicate_screen": "Exact SHA-256 duplicates grouped; within-person OpenCV pHash pairs at Hamming distance <= 2 kept in the same split.",
        },
        "model": {
            "version": str(test["model_version"]),
            "threshold": threshold,
            "threshold_source": "Selected on validation and locked before test.",
            "min_margin": float(test["min_margin"]),
            "camera": str(tm["camera"]),
            "device": str(tm["device"]),
        },
        "validation": {
            "query_count": int(validation["query_count"]),
            "known_query_count": int(validation["known_query_count"]),
            "unknown_query_count": int(validation["unknown_query_count"]),
            "known_top1_accuracy": float(validation["known_top1_accuracy"]),
            "macro_f1": float(validation["macro_f1"]),
            "unknown_fpir": float(validation["unknown_fpir"]),
            "known_identification_failures": val_known_errors,
            "unknown_false_accepts": val_fp_count,
            "query_detection_or_encoding_failures": int(validation["detection_or_encoding_failures"]),
            "selected_threshold": threshold,
            "unknown_fpir_target": float(validation["validation_constraint_max_unknown_fpir"]),
        },
        "test": {
            "query_count": int(test["query_count"]),
            "known_query_count": int(test["known_query_count"]),
            "unknown_query_count": int(test["unknown_query_count"]),
            "known_identities": int(tm["known_identities"]),
            "unknown_identities": int(tm["unknown_identities"]),
            "known_top1_accuracy": known_top1,
            "known_top1_correct": int(round(known_top1 * int(test["known_query_count"]))),
            "known_identification_failures": known_errors,
            "macro_f1": macro_f1,
            "unknown_fpir": unknown_fpir,
            "unknown_false_accepts": int(round(unknown_fpir * int(test["unknown_query_count"]))),
            "gallery_identities": int(test["gallery_person_count"]),
            "gallery_templates_encoded": int(test["gallery_template_count"]),
            "gallery_detection_or_encoding_failures": int(test["gallery_detection_or_encoding_failures"]),
            "known_query_detection_or_encoding_failures": known_detect_failures,
            "unknown_query_detection_or_encoding_failures": unknown_detect_failures,
            "all_query_detection_or_encoding_failures": int(test["detection_or_encoding_failures"]),
            "threshold": threshold,
            "known_top1_exceeds_80_percent": known_top1 > 0.80,
        },
        "scope_note": "This FEI still-image benchmark has no documented capture sessions or camera/lens metadata; it does not validate performance under the project's live camera protocol.",
    }


def write_outputs(validation: dict[str, object], test: dict[str, object], report: dict[str, object], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    # This JSON is an aggregate summary only: no person IDs, image paths, predictions, per-class metrics, or confusion table.
    (output / "poster_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    columns = ["metric", "value", "split", "note"]
    rows = [
        ["dataset", report["dataset"]["name"], "all", f"Official source: {FEI_SOURCE}; research-use only, no redistribution."],
        ["split_seed", 20261108, "all", "Fixed deterministic person-level split."],
        ["capture_sessions", "not documented", "all", "Individual-image benchmark; no session grouping."],
        ["known_identities", 100, "gallery/validation/test", "Four gallery, five validation, five test images per identity."],
        ["validation_unknown_identities", 50, "validation", "Separate from the test-only unknown identities."],
        ["test_unknown_identities", 50, "test", "Fourteen test images per test-only unknown identity."],
        ["gallery_templates_encoded", report["test"]["gallery_templates_encoded"], "gallery", "Six of 400 gallery images failed detection or encoding."],
        ["selected_threshold", report["model"]["threshold"], "validation", "Locked before test; max validation FPIR 5%."],
        ["known_top1_accuracy", report["validation"]["known_top1_accuracy"], "validation", "500 known queries; detection failures count as errors."],
        ["macro_f1", report["validation"]["macro_f1"], "validation", "101 classes including Unknown."],
        ["unknown_fpir", report["validation"]["unknown_fpir"], "validation", "1 false accept / 700 unknown queries."],
        ["known_top1_accuracy", report["test"]["known_top1_accuracy"], "test", "493 correct / 500 known queries; exceeds 80%."],
        ["macro_f1", report["test"]["macro_f1"], "test", "101 classes including Unknown."],
        ["unknown_fpir", report["test"]["unknown_fpir"], "test", "0 false accepts / 700 unknown queries."],
        ["known_identification_failures", report["test"]["known_identification_failures"], "test", "Includes known-face detection or encoding failures."],
        ["known_query_detection_or_encoding_failures", report["test"]["known_query_detection_or_encoding_failures"], "test", "Counted as known-identification errors."],
        ["unknown_query_detection_or_encoding_failures", report["test"]["unknown_query_detection_or_encoding_failures"], "test", "Aggregate detector/encoder failures among unknown queries."],
        ["gallery_detection_or_encoding_failures", report["test"]["gallery_detection_or_encoding_failures"], "gallery", "Counted separately from query failures."],
        ["test_queries", report["test"]["query_count"], "test", "500 known + 700 unknown queries."],
    ]
    with (output / "poster_metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(rows)

    # Pass only aggregate validation values to the threshold-plot writer.
    curve = validation.get("threshold_curve")
    curve_report = {
        "split": "validation",
        "threshold_curve": curve,
        "query_count": int(validation["query_count"]),
        "selected_threshold": float(validation["selected_threshold"]),
        "min_margin": float(validation["min_margin"]),
    }
    (output / "accuracy_fpir_threshold.svg").write_text(_threshold_svg(curve_report), encoding="utf-8")
    (output / "confusion_matrix.svg").write_text(_confusion_svg(test), encoding="utf-8")
    (output / "system_flow.svg").write_text(_flow_svg(), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-report", type=Path, required=True)
    parser.add_argument("--test-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/public"))
    args = parser.parse_args()
    validation, test = _load(args.validation_report), _load(args.test_report)
    report = build(validation, test)
    write_outputs(validation, test, report, args.output_dir)
    print(json.dumps(report["test"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
