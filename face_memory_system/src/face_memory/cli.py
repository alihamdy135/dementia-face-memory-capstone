from __future__ import annotations

import argparse
import json
from pathlib import Path
import os
import sys

from .opencv_backend import OpenCVFaceEncoder
from .service import FaceMemoryService
from .store import MemoryStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = Path(os.environ.get("FACE_MEMORY_MODEL_DIR", PROJECT_ROOT / "models"))
DEFAULT_YUNET = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
DEFAULT_SFACE = MODEL_DIR / "face_recognition_sface_2021dec.onnx"
DEFAULT_DB = PROJECT_ROOT / "data" / "face_memory.sqlite3"


def _add_store_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Local SQLite database path")


def _add_model_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--yunet", type=Path, default=DEFAULT_YUNET, help="YuNet ONNX path")
    parser.add_argument("--sface", type=Path, default=DEFAULT_SFACE, help="SFace ONNX path")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline consent-based face memory prototype")
    subparsers = parser.add_subparsers(dest="command", required=True)

    enroll = subparsers.add_parser("enroll", help="Enroll or add another image for a person")
    _add_store_options(enroll)
    _add_model_options(enroll)
    enroll.add_argument("--image", type=Path, required=True)
    enroll.add_argument("--person-id", required=True)
    enroll.add_argument("--name", required=True)
    enroll.add_argument("--relationship", required=True)

    recognize = subparsers.add_parser("recognize", help="Identify one face and retrieve its profile")
    _add_store_options(recognize)
    _add_model_options(recognize)
    recognize.add_argument("--image", type=Path, required=True)
    recognize.add_argument(
        "--threshold",
        type=float,
        required=True,
        help="Cosine threshold calibrated on validation data; do not copy the LFW default blindly",
    )

    add_memory = subparsers.add_parser("add-memory", help="Add a caregiver note or audio reference")
    _add_store_options(add_memory)
    add_memory.add_argument("--person-id", required=True)
    add_memory.add_argument("--text", default="")
    add_memory.add_argument("--audio", type=Path)
    add_memory.add_argument("--source", default="caregiver")

    show = subparsers.add_parser("show", help="Show one person's profile and stored memories")
    _add_store_options(show)
    show.add_argument("--person-id", required=True)

    delete = subparsers.add_parser("delete", help="Delete a person and their local face templates and memories")
    _add_store_options(delete)
    delete.add_argument("--person-id", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        store = MemoryStore(args.db)
        if args.command == "enroll":
            encoder = OpenCVFaceEncoder(args.yunet, args.sface)
            service = FaceMemoryService(encoder, store, threshold=None)
            result = service.enroll_image(
                args.image, args.person_id, args.name, args.relationship
            )
            print(json.dumps({"enrolled": result, "image": str(args.image)}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "recognize":
            encoder = OpenCVFaceEncoder(args.yunet, args.sface)
            service = FaceMemoryService(encoder, store, threshold=args.threshold)
            result = service.recognize_image(args.image)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "add-memory":
            store.add_memory(
                args.person_id,
                args.text,
                str(args.audio) if args.audio else None,
                args.source,
            )
            print(json.dumps({"saved": True, "person_id": args.person_id}, ensure_ascii=False))
            return 0
        if args.command == "show":
            result = {
                "person": store.get_person(args.person_id),
                "memories": store.get_memories(args.person_id),
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "delete":
            deleted = store.delete_person(args.person_id)
            print(json.dumps({"deleted": deleted, "person_id": args.person_id}, ensure_ascii=False))
            return 0
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
