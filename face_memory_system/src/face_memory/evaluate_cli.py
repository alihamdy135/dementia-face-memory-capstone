from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .cli import DEFAULT_SFACE, DEFAULT_YUNET
from .evaluation import evaluate_manifest
from .opencv_backend import OpenCVFaceEncoder
from .settings import MIN_MARGIN, UNKNOWN_FPIR_TARGET
from .settings import MODEL_VERSION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate known and unknown face identification")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--mode", choices=["calibrate", "test"], required=True)
    parser.add_argument("--max-unknown-fpir", type=float)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--validation-report", type=Path, help="Locked validation JSON required for test mode")
    parser.add_argument("--min-margin", type=float, default=MIN_MARGIN)
    parser.add_argument("--camera", default="not recorded")
    parser.add_argument("--device", default="not recorded")
    parser.add_argument(
        "--allow-unrecorded-sessions",
        action="store_true",
        help="Benchmark-only: allow all session_id cells to remain blank when the source has no session metadata",
    )
    parser.add_argument("--dataset-name")
    parser.add_argument("--protocol-note")
    parser.add_argument("--yunet", type=Path, default=DEFAULT_YUNET)
    parser.add_argument("--sface", type=Path, default=DEFAULT_SFACE)
    parser.add_argument("--output", type=Path, help="Optional private JSON report path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.mode == "calibrate":
            if args.max_unknown_fpir is None or args.threshold is not None:
                print("Calibration requires --max-unknown-fpir and forbids --threshold", file=sys.stderr)
                return 2
            report = evaluate_manifest(
                args.manifest,
                OpenCVFaceEncoder(args.yunet, args.sface),
                split="validation",
                max_unknown_fpir=args.max_unknown_fpir,
                min_margin=args.min_margin,
                camera=args.camera,
                device=args.device,
                allow_unrecorded_sessions=args.allow_unrecorded_sessions,
                dataset_name=args.dataset_name,
                protocol_note=args.protocol_note,
            )
        else:
            if args.max_unknown_fpir is not None or args.validation_report is None:
                print("Test evaluation requires --validation-report from validation", file=sys.stderr)
                return 2
            locked = json.loads(args.validation_report.read_text(encoding="utf-8"))
            if locked.get("split") != "validation" or locked.get("selected_threshold") is None:
                print("The provided JSON is not a validation calibration report", file=sys.stderr)
                return 2
            if locked.get("model_version") != MODEL_VERSION or float(locked.get("min_margin", -1)) != args.min_margin:
                print("Model version or min_margin differs from the locked validation run", file=sys.stderr)
                return 2
            locked_metadata = locked.get("metadata") or {}
            if bool(args.allow_unrecorded_sessions) != (
                locked_metadata.get("capture_session_metadata", "").startswith("not_documented;")
            ):
                print("Session-metadata handling must match the locked validation run", file=sys.stderr)
                return 2
            if args.dataset_name != locked_metadata.get("dataset_name"):
                print("Dataset name must match the locked validation run", file=sys.stderr)
                return 2
            if args.protocol_note != locked_metadata.get("protocol_note"):
                print("Protocol note must match the locked validation run", file=sys.stderr)
                return 2
            locked_threshold = float(locked["selected_threshold"])
            if args.threshold is not None and args.threshold != locked_threshold:
                print("--threshold must match the threshold selected on validation", file=sys.stderr)
                return 2
            report = evaluate_manifest(
                args.manifest,
                OpenCVFaceEncoder(args.yunet, args.sface),
                split="test",
                threshold=locked_threshold,
                min_margin=args.min_margin,
                camera=args.camera,
                device=args.device,
                allow_unrecorded_sessions=args.allow_unrecorded_sessions,
                dataset_name=args.dataset_name,
                protocol_note=args.protocol_note,
            )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    output = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
        from .poster_artifacts import write_poster_artifacts

        write_poster_artifacts(args.output.parent, report)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
