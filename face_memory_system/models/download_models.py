#!/usr/bin/env python3
"""Download pinned OpenCV Zoo model files and verify their SHA-256 digests."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen


REVISION = "d4938dfc9d4ec5d098bfa33e98b3f3345a236586"
MODELS = {
    "face_detection_yunet_2023mar.onnx": (
        "face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
    "face_recognition_sface_2021dec.onnx": (
        "face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for filename, (source_path, expected_hash) in MODELS.items():
        destination = directory / filename
        if destination.is_file() and sha256(destination) == expected_hash:
            print(f"Verified {filename}")
            continue

        url = f"https://huggingface.co/opencv/opencv_zoo/resolve/{REVISION}/models/{source_path}?download=true"
        request = Request(url, headers={"User-Agent": "dementia-face-memory-model-setup/1.0"})
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            try:
                with urlopen(request, timeout=60) as response:
                    while block := response.read(1024 * 1024):
                        temporary.write(block)
                actual_hash = sha256(temporary_path)
                if actual_hash != expected_hash:
                    raise ValueError(f"SHA-256 mismatch for {filename}: {actual_hash}")
                os.replace(temporary_path, destination)
            except Exception:
                temporary_path.unlink(missing_ok=True)
                raise
        print(f"Downloaded and verified {filename}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    download(args.directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
