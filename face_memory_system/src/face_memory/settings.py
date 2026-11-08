"""Versioned settings shared by the web service, evaluator, and Pi runtime."""

from __future__ import annotations

import json
import os
from pathlib import Path


SETTINGS_PATH = Path(
    os.environ.get("FACE_MEMORY_SETTINGS_PATH", Path(__file__).resolve().parents[2] / "config" / "model-v1.json")
)
_SETTINGS = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))

MODEL_VERSION = str(_SETTINGS["model"]["version"])
DETECTOR_SCORE_THRESHOLD = float(_SETTINGS["detector"]["score_threshold"])
DETECTOR_NMS_THRESHOLD = float(_SETTINGS["detector"]["nms_threshold"])
IDENTITY_THRESHOLD = float(_SETTINGS["matcher"]["provisional_threshold"])
MIN_MARGIN = float(_SETTINGS["matcher"]["min_margin"])
THRESHOLD_STATUS = str(_SETTINGS["matcher"]["threshold_status"])
UNKNOWN_FPIR_TARGET = float(_SETTINGS["evaluation"]["unknown_fpir_target"])
