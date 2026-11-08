"""Internal, memory-only HTTP service for face processing and optional transcription."""

from __future__ import annotations

import base64
import hmac
import io
import os
import shutil
import subprocess
import threading
import wave

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .cli import DEFAULT_SFACE, DEFAULT_YUNET
from .core import IdentityMatcher
from .opencv_backend import FaceEncoderError, MultipleFacesError, NoFaceError, OpenCVFaceEncoder
from .settings import IDENTITY_THRESHOLD, MIN_MARGIN, MODEL_VERSION, THRESHOLD_STATUS


class RecognitionRequest(BaseModel):
    image_base64: str = Field(min_length=1, max_length=18_000_000)
    gallery: dict[str, list[list[float]]]
    threshold: float = IDENTITY_THRESHOLD
    min_margin: float = MIN_MARGIN


class TranscriptionRequest(BaseModel):
    audio_base64: str = Field(min_length=1, max_length=28_000_000)


app = FastAPI(title="Face Memory Local Model API", version=MODEL_VERSION)
_encoder: OpenCVFaceEncoder | None = None
_encoder_lock = threading.Lock()
_whisper_model = None
_whisper_lock = threading.Lock()


@app.middleware("http")
async def protect_remote_model_calls(request: Request, call_next):
    expected = os.environ.get("MODEL_SERVICE_TOKEN", "")
    if expected and request.url.path in {"/encode", "/recognize", "/transcribe"}:
        supplied = request.headers.get("x-model-token", "")
        if not hmac.compare_digest(supplied, expected):
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
    return await call_next(request)


@app.on_event("startup")
def load_models() -> None:
    global _encoder
    if _encoder is None:
        _encoder = OpenCVFaceEncoder(DEFAULT_YUNET, DEFAULT_SFACE)


def _get_encoder() -> OpenCVFaceEncoder:
    global _encoder
    if _encoder is None:
        with _encoder_lock:
            if _encoder is None:
                _encoder = OpenCVFaceEncoder(DEFAULT_YUNET, DEFAULT_SFACE)
    return _encoder


@app.get("/health")
def health() -> dict[str, object]:
    try:
        _get_encoder()
        model_ready = True
    except Exception:
        model_ready = False
    try:
        import whisper  # type: ignore[import-not-found]

        transcription_available = bool(whisper)
    except ImportError:
        transcription_available = False
    return {
        "status": "ready" if model_ready else "model_unavailable",
        "model_version": MODEL_VERSION,
        "threshold_status": THRESHOLD_STATUS,
        "provisional_threshold": IDENTITY_THRESHOLD,
        "min_margin": MIN_MARGIN,
        "transcription_available": transcription_available,
    }


@app.post("/encode")
async def encode(request: Request) -> dict[str, object]:
    raw = await request.body()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(413, "image_too_large")
    try:
        encoder = _get_encoder()
        with _encoder_lock:
            vector = encoder.encode_bytes(raw)
    except NoFaceError:
        raise HTTPException(422, "no_face") from None
    except MultipleFacesError:
        raise HTTPException(422, "multiple_faces") from None
    except (ValueError, FileNotFoundError):
        raise HTTPException(422, "invalid_image") from None
    except FaceEncoderError:
        raise HTTPException(503, "model_error") from None
    return {"embedding": vector, "model_version": MODEL_VERSION}


@app.post("/recognize")
def recognize(body: RecognitionRequest) -> dict[str, object]:
    try:
        raw = base64.b64decode(body.image_base64, validate=True)
    except Exception:
        raise HTTPException(422, "invalid_image") from None
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(413, "image_too_large")
    try:
        encoder = _get_encoder()
        with _encoder_lock:
            vector = encoder.encode_bytes(raw)
    except NoFaceError:
        raise HTTPException(422, "no_face") from None
    except MultipleFacesError:
        raise HTTPException(422, "multiple_faces") from None
    except (ValueError, FileNotFoundError):
        raise HTTPException(422, "invalid_image") from None
    except FaceEncoderError:
        raise HTTPException(503, "model_error") from None
    result = IdentityMatcher(body.threshold, body.min_margin).match(vector, body.gallery)
    return {
        "status": result.status,
        "person_id": result.person_id,
        "score": result.score,
        "second_score": result.second_score,
        "margin": result.score - result.second_score,
        "model_version": MODEL_VERSION,
        "threshold_status": THRESHOLD_STATUS,
    }


@app.post("/transcribe")
def transcribe(body: TranscriptionRequest) -> dict[str, str]:
    global _whisper_model
    try:
        audio = base64.b64decode(body.audio_base64, validate=True)
    except Exception:
        raise HTTPException(422, "invalid_audio") from None
    if len(audio) > 20 * 1024 * 1024:
        raise HTTPException(413, "audio_too_large")
    try:
        import numpy as np
        import whisper  # type: ignore[import-not-found]
    except ImportError:
        raise HTTPException(503, "transcription_unavailable") from None
    try:
        try:
            with wave.open(io.BytesIO(audio), "rb") as wav:
                channels = wav.getnchannels()
                if channels not in (1, 2) or wav.getsampwidth() != 2:
                    raise ValueError("Unsupported WAV encoding")
                rate = wav.getframerate()
                frames = wav.readframes(wav.getnframes())
        except wave.Error:
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise HTTPException(503, "transcription_decoder_unavailable") from None
            decoded = subprocess.run(
                [ffmpeg, "-nostdin", "-v", "error", "-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"],
                input=audio,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=45,
            ).stdout
            channels, rate, frames = 1, 16000, decoded
        if rate <= 0 or len(frames) > rate * 2 * 60 * 10:
            raise ValueError("Audio duration is invalid")
        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        if channels == 2:
            samples = samples.reshape(-1, 2)
        if len(samples) == 0:
            raise ValueError("Audio is empty")
        if len(samples.shape) == 2:
            samples = samples.mean(axis=1)
        if rate != 16000:
            try:
                import scipy.signal

                samples = scipy.signal.resample_poly(samples, 16000, rate).astype(np.float32)
            except ImportError:
                raise HTTPException(503, "transcription_audio_resampler_unavailable") from None
        if _whisper_model is None:
            with _whisper_lock:
                if _whisper_model is None:
                    _whisper_model = whisper.load_model("small", device="cpu")
        result = _whisper_model.transcribe(samples, language="ar", fp16=False)
    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(503, "transcription_failed") from None
    except Exception:
        raise HTTPException(422, "transcription_failed") from None
    return {"text": str(result.get("text", "")).strip(), "language": "ar"}


