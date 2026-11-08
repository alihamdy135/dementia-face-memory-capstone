from __future__ import annotations

from pathlib import Path
from typing import Any

from .settings import DETECTOR_NMS_THRESHOLD, DETECTOR_SCORE_THRESHOLD


class FaceEncoderError(RuntimeError):
    """Base exception for face detection or embedding errors."""


class NoFaceError(FaceEncoderError):
    pass


class MultipleFacesError(FaceEncoderError):
    pass


class OpenCVFaceEncoder:
    """Offline YuNet detector plus SFace embedding extractor."""

    def __init__(
        self,
        detector_model: str | Path,
        recognizer_model: str | Path,
        score_threshold: float = DETECTOR_SCORE_THRESHOLD,
        nms_threshold: float = DETECTOR_NMS_THRESHOLD,
        top_k: int = 5000,
    ) -> None:
        self.detector_model = Path(detector_model)
        self.recognizer_model = Path(recognizer_model)
        for model_path in (self.detector_model, self.recognizer_model):
            if not model_path.is_file():
                raise FileNotFoundError(f"Required ONNX model not found: {model_path}")

        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise RuntimeError(
                "Install the package dependencies with `python -m pip install -r requirements.txt`"
            ) from exc
        self._cv2 = cv2
        self._np = np

        detector_factory: Any = getattr(cv2, "FaceDetectorYN", None)
        if detector_factory is not None and hasattr(detector_factory, "create"):
            self.detector = detector_factory.create(
                str(self.detector_model),
                "",
                (320, 320),
                score_threshold,
                nms_threshold,
                top_k,
            )
        elif hasattr(cv2, "FaceDetectorYN_create"):
            self.detector = cv2.FaceDetectorYN_create(
                str(self.detector_model),
                "",
                (320, 320),
                score_threshold,
                nms_threshold,
                top_k,
            )
        else:
            raise RuntimeError("This OpenCV build does not include FaceDetectorYN")

        recognizer_factory: Any = getattr(cv2, "FaceRecognizerSF", None)
        if recognizer_factory is not None and hasattr(recognizer_factory, "create"):
            self.recognizer = recognizer_factory.create(str(self.recognizer_model), "")
        elif hasattr(cv2, "FaceRecognizerSF_create"):
            self.recognizer = cv2.FaceRecognizerSF_create(str(self.recognizer_model), "")
        else:
            raise RuntimeError("This OpenCV build does not include FaceRecognizerSF")

    def encode_image(self, image_path: str | Path) -> list[float]:
        image_path = Path(image_path)
        image = self._cv2.imread(str(image_path), self._cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"Could not read image: {image_path}")
        return self.encode_frame(image)

    def encode_bytes(self, image_bytes: bytes) -> list[float]:
        if not image_bytes:
            raise ValueError("Image data is empty")
        image = self._cv2.imdecode(
            self._np.frombuffer(image_bytes, dtype=self._np.uint8), self._cv2.IMREAD_COLOR
        )
        if image is None:
            raise ValueError("Image data could not be decoded")
        return self.encode_frame(image)

    def encode_frame(self, frame: Any) -> list[float]:
        if frame is None or getattr(frame, "ndim", 0) != 3 or frame.shape[2] != 3:
            raise ValueError("Expected a non-empty BGR image with three color channels")
        height, width = frame.shape[:2]
        if height <= 0 or width <= 0:
            raise ValueError("Image dimensions must be positive")

        self.detector.setInputSize((width, height))
        _, faces = self.detector.detect(frame)
        if faces is None or len(faces) == 0:
            raise NoFaceError("No face detected; no identity was assigned")
        if len(faces) != 1:
            raise MultipleFacesError(
                "Multiple faces detected; provide a single-person crop to avoid misidentification"
            )

        aligned = self.recognizer.alignCrop(frame, faces[0])
        feature = self.recognizer.feature(aligned).reshape(-1).astype(self._np.float32)
        norm = float(self._np.linalg.norm(feature))
        if not self._np.isfinite(norm) or norm == 0.0:
            raise FaceEncoderError("The recognizer returned an invalid face embedding")
        normalized = feature / norm
        return [float(value) for value in normalized]
