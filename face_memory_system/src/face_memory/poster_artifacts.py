"""Create poster-ready, anonymous SVG/CSV summaries from evaluation reports."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import html


METRIC_TARGETS = {
    "known_top1_accuracy": ("≥ 80%", 0.80),
    "macro_f1": ("≥ 0.80 (proposed)", 0.80),
    "unknown_fpir": ("≤ 5% (proposed)", 0.05),
}


def pending_report() -> dict[str, object]:
    return {
        "status": "awaiting_authorized_test_data",
        "status_label": "Awaiting evaluation data",
        "data_note": "No consented evaluation image manifest was supplied; no performance value is measured.",
        "model_version": "yunet-sface-2021dec-v1",
        "threshold": None,
        "min_margin": 0.02,
        "sample_size": 0,
        "camera": "not recorded",
        "device": "not recorded",
        "known_query_count": 0,
        "unknown_query_count": 0,
        "detection_or_encoding_failures": None,
        "pi_audio_response_max_ms": None,
        "pi_audio_response_p95_ms": None,
        "pi_hardware_status": "awaiting_pi2_hardware_test",
        "metrics": {
            metric: {"value": None, "status": "not_measured", "target": target}
            for metric, (target, _) in METRIC_TARGETS.items()
        },
    }


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _waiting_svg(title: str, detail: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="560" viewBox="0 0 1000 560" role="img" aria-labelledby="title desc">
<title id="title">{_escape(title)}</title><desc id="desc">{_escape(detail)}</desc>
<rect width="1000" height="560" rx="28" fill="#f8f6fb"/><rect x="32" y="32" width="936" height="496" rx="20" fill="#fff" stroke="#e6dfee"/>
<text x="500" y="100" text-anchor="middle" font-family="Arial,sans-serif" font-size="28" fill="#241b38">{_escape(title)}</text>
<rect x="280" y="185" width="440" height="164" rx="18" fill="#f0e8fb" stroke="#d9befc" stroke-dasharray="8 8"/>
<circle cx="500" cy="236" r="24" fill="#d9befc"/><path d="M500 222v18m0 9v.1" stroke="#633da4" stroke-width="4" stroke-linecap="round"/>
<text x="500" y="296" text-anchor="middle" font-family="Arial,sans-serif" font-size="22" font-weight="700" fill="#633da4">Awaiting evaluation data</text>
<text x="500" y="382" text-anchor="middle" font-family="Arial,sans-serif" font-size="16" fill="#625970">{_escape(detail)}</text>
<text x="500" y="474" text-anchor="middle" font-family="Arial,sans-serif" font-size="13" fill="#625970">No authorized gallery, validation, and test sessions provided</text></svg>'''


def _threshold_svg(report: dict[str, object] | None) -> str:
    curve = report.get("threshold_curve") if report else None
    if not curve or (report or {}).get("split") != "validation":
        return _waiting_svg(
            "Accuracy / FPIR vs Threshold",
            "Select a threshold on validation data after collecting consented images from separate capture sessions.",
        )
    points = [item for item in curve if isinstance(item, dict)]
    x_values = [float(item["threshold"]) for item in points]
    x_min, x_max = min(x_values), max(x_values)
    if x_min == x_max:
        x_min -= 0.01
        x_max += 0.01
    left, top, width, height = 105, 82, 800, 330

    def point(value_x: float, value_y: float) -> tuple[float, float]:
        return left + (value_x - x_min) / (x_max - x_min) * width, top + (1 - max(0, min(1, value_y))) * height

    grid = []
    for tick in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
        y = top + (1 - tick) * height
        grid.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+width}" y2="{y:.1f}" stroke="#e6dfee"/><text x="{left-16}" y="{y+5:.1f}" text-anchor="end" font-size="13" fill="#625970">{tick:.0%}</text>')
    accuracy = " ".join(f"{x:.1f},{y:.1f}" for x, y in [point(float(item["threshold"]), float(item["known_top1_accuracy"])) for item in points])
    fpir = " ".join(f"{x:.1f},{y:.1f}" for x, y in [point(float(item["threshold"]), float(item["unknown_fpir"])) for item in points])
    title = f"Validation · n={report.get('query_count', 0)} · threshold={report.get('selected_threshold', 'not set')}"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="560" viewBox="0 0 1000 560" role="img">
<rect width="1000" height="560" rx="24" fill="#fff"/><text x="500" y="45" text-anchor="middle" font-family="Arial,sans-serif" font-size="25" font-weight="700" fill="#241b38">Accuracy / FPIR vs Threshold</text>
<text x="500" y="68" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" fill="#625970">{_escape(title)} · margin={_escape(report.get('min_margin', 0))}</text>
{''.join(grid)}<line x1="{left}" y1="{top+height}" x2="{left+width}" y2="{top+height}" stroke="#b7aac9"/><line x1="{left}" y1="{top}" x2="{left}" y2="{top+height}" stroke="#b7aac9"/>
<polyline fill="none" stroke="#633da4" stroke-width="4" stroke-linejoin="round" points="{accuracy}"/><polyline fill="none" stroke="#cf8a55" stroke-width="4" stroke-linejoin="round" points="{fpir}"/>
<text x="500" y="465" text-anchor="middle" font-family="Arial,sans-serif" font-size="14" fill="#625970">Cosine similarity threshold</text>
<line x1="345" y1="510" x2="378" y2="510" stroke="#633da4" stroke-width="4"/><text x="385" y="515" font-family="Arial,sans-serif" font-size="13" fill="#625970">Known top-1 accuracy</text><line x1="575" y1="510" x2="608" y2="510" stroke="#5569ae" stroke-width="4"/><text x="615" y="515" font-family="Arial,sans-serif" font-size="13" fill="#625970">Unknown FPIR</text></svg>'''


def _confusion_svg(report: dict[str, object] | None) -> str:
    matrix = report.get("confusion_matrix") if report else None
    if not matrix or (report or {}).get("split") != "test":
        return _waiting_svg("Test Confusion Matrix", "Volunteer IDs will appear as anonymous labels after independent testing.")
    matrix = matrix  # type: ignore[assignment]
    labels = sorted(matrix)
    display = {label: ("Unknown" if label == "<unknown>" else f"ID-{index:02d}") for index, label in enumerate([item for item in labels if item != "<unknown>"], 1)}
    if "<unknown>" in matrix:
        display["<unknown>"] = "Unknown"
    cell = min(92, 620 // max(1, len(labels)))
    origin_x, origin_y = 260, 150
    max_value = max((int(matrix[a][p]) for a in labels for p in labels), default=0)
    cells = []
    labels_svg = []
    for col, label in enumerate(labels):
        x = origin_x + col * cell + cell / 2
        labels_svg.append(f'<text x="{x}" y="{origin_y-15}" text-anchor="middle" font-size="12" fill="#625970">{display[label]}</text>')
    for row, actual in enumerate(labels):
        y = origin_y + row * cell + cell / 2
        labels_svg.append(f'<text x="{origin_x-17}" y="{y+4}" text-anchor="end" font-size="12" fill="#625970">{display[actual]}</text>')
        for col, predicted in enumerate(labels):
            value = int(matrix[actual][predicted])
            if value == 0:
                continue
            opacity = 0.07 + (value / max_value * 0.65 if max_value else 0)
            color = "#34745e" if actual == predicted else "#cf8a55"
            x, y0 = origin_x + col * cell, origin_y + row * cell
            cells.append(f'<rect x="{x}" y="{y0}" width="{cell-3}" height="{cell-3}" rx="7" fill="{color}" fill-opacity="{opacity:.2}"/><text x="{x+cell/2-1.5}" y="{y0+cell/2+5}" text-anchor="middle" font-size="14" font-weight="700" fill="#241b38">{value}</text>')
    width = max(850, origin_x + len(labels) * cell + 35)
    height = max(480, origin_y + len(labels) * cell + 60)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img"><rect width="100%" height="100%" rx="22" fill="#fff"/><text x="{width/2}" y="50" text-anchor="middle" font-family="Arial,sans-serif" font-size="24" font-weight="700" fill="#241b38">Test Confusion Matrix</text><text x="{width/2}" y="76" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" fill="#625970">IDs anonymized · n={report.get('query_count', 0)}</text>{''.join(labels_svg)}{''.join(cells)}<text x="{origin_x+len(labels)*cell/2}" y="{origin_y+len(labels)*cell+32}" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" fill="#625970">Predicted identity</text></svg>'''


def _flow_svg() -> str:
    boxes = [
        (810, "Camera / image", "Single face"), (610, "Next.js", "Private account + API"),
        (410, "FastAPI", "YuNet + SFace"), (210, "MongoDB", "Embeddings + records"),
    ]
    items = []
    for x, title, detail in boxes:
        items.append(f'<rect x="{x}" y="170" width="150" height="92" rx="16" fill="#f0e8fb" stroke="#d9befc"/><text x="{x+75}" y="207" text-anchor="middle" font-size="18" font-weight="700" fill="#503183">{_escape(title)}</text><text x="{x+75}" y="235" text-anchor="middle" font-size="12" fill="#625970">{_escape(detail)}</text>')
    for x in (775, 575, 375):
        items.append(f'<path d="M{x} 216h-18m0 0 7-7m-7 7 7 7" stroke="#8066b4" stroke-width="2.5" fill="none"/>')
    items.append('<rect x="284" y="342" width="420" height="66" rx="15" fill="#fbe9df" stroke="#efd1c2"/><text x="494" y="370" text-anchor="middle" font-size="16" font-weight="700" fill="#704d42">Pi 2 · SQLite + WAV · works offline</text><text x="494" y="392" text-anchor="middle" font-size="11" fill="#625970">Queued events sync when a connection returns</text><path d="M285 374H180V286H885V272" stroke="#c88e70" stroke-dasharray="6 6" stroke-width="2" fill="none"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="500" viewBox="0 0 1000 500" role="img"><rect width="1000" height="500" rx="24" fill="#fff"/><text x="500" y="76" text-anchor="middle" font-family="Arial,sans-serif" font-size="27" font-weight="700" fill="#241b38">System flow · local processing and matching</text>{''.join(items)}<text x="500" y="458" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" fill="#859289">Images are not retained · audio plays only after a confirmed match</text></svg>'''


def write_poster_artifacts(output_dir: str | Path, report: dict[str, object] | None = None) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    if report is None:
        report = pending_report()
    (out / "poster_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    metrics = report.get("metrics") or report
    metadata = report.get("metadata") or {}
    output_rows = []
    for metric, (target, _) in METRIC_TARGETS.items():
        value = metrics.get(metric) if isinstance(metrics, dict) else None
        status = "measured" if isinstance(value, (int, float)) else "not_measured"
        output_rows.append([metric, value if status == "measured" else "", target, status, report.get("query_count", 0)])
    output_rows.extend([
        ["sample_size", report.get("query_count", report.get("sample_size", 0)), "record actual N", "reported", report.get("query_count", 0)],
        ["gallery_people", report.get("gallery_person_count", ""), "record actual count", "reported" if report.get("gallery_person_count") is not None else "not_measured", ""],
        ["known_queries", report.get("known_query_count", ""), "record actual count", "reported" if report.get("known_query_count") is not None else "not_measured", ""],
        ["unknown_queries", report.get("unknown_query_count", ""), "record actual count", "reported" if report.get("unknown_query_count") is not None else "not_measured", ""],
        ["detection_or_encoding_failures", report.get("detection_or_encoding_failures", ""), "report all failures", "reported" if report.get("detection_or_encoding_failures") is not None else "not_measured", ""],
        ["camera", metadata.get("camera", report.get("camera", "not recorded")), "record model and lens", "reported", ""],
        ["device", metadata.get("device", report.get("device", "not recorded")), "record actual device", "reported", ""],
        ["pi_audio_response_max_ms", report.get("pi_audio_response_max_ms", ""), "measure at Pi 2 speaker", "not_measured" if report.get("pi_audio_response_max_ms") is None else "measured", ""],
        ["pi_audio_response_p95_ms", report.get("pi_audio_response_p95_ms", ""), "measure at Pi 2 speaker", "not_measured" if report.get("pi_audio_response_p95_ms") is None else "measured", ""],
    ])
    with (out / "poster_metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["metric", "value", "target", "status", "sample_size"])
        writer.writerows(output_rows)
    (out / "confusion_matrix.svg").write_text(_confusion_svg(report), encoding="utf-8")
    (out / "accuracy_fpir_threshold.svg").write_text(_threshold_svg(report), encoding="utf-8")
    (out / "system_flow.svg").write_text(_flow_svg(), encoding="utf-8")
