#!/usr/bin/env python3
"""Offline Pi 2 runner, sharing the website/evaluator YuNet-SFace pipeline."""

from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import statistics
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
import uuid


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "face_memory_system" / "src"))

from face_memory.core import IdentityMatcher  # noqa: E402
from face_memory.opencv_backend import OpenCVFaceEncoder, NoFaceError, MultipleFacesError  # noqa: E402
from face_memory.settings import IDENTITY_THRESHOLD, MIN_MARGIN, MODEL_VERSION  # noqa: E402


DB_PATH = Path(os.environ.get("FACE_MEMORY_PI_DB", Path.home() / ".local/share/face-memory/face-memory.sqlite3"))
AUDIO_DIR = Path(os.environ.get("FACE_MEMORY_PI_AUDIO_DIR", Path.home() / ".local/share/face-memory/audio"))
DEVICE_ID = os.environ.get("FACE_MEMORY_DEVICE_ID", "pi2-face-memory")


class PiStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.executescript("""
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS people (
                    person_id TEXT PRIMARY KEY, name TEXT NOT NULL, relationship TEXT NOT NULL,
                    model_version TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS face_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_id TEXT NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
                    embedding_json TEXT NOT NULL, model_version TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS event_queue (
                    event_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def import_person(self, payload: dict[str, object]) -> None:
        if payload.get("schemaVersion") != 1 or payload.get("modelVersion") != MODEL_VERSION:
            raise ValueError("Export schema or model version does not match this Pi build")
        person = payload.get("person")
        if not isinstance(person, dict):
            raise ValueError("Export file has no person object")
        person_id = str(person.get("personId", "")).strip()
        name = str(person.get("name", "")).strip()
        relationship = str(person.get("relationship", "")).strip()
        templates = person.get("templates")
        if not person_id or not name or not relationship or not isinstance(templates, list) or not templates:
            raise ValueError("Export needs person ID, name, relationship, and face templates")
        normalized = []
        for template in templates:
            vector = [float(value) for value in template]
            if not vector or not all(value == value and abs(value) < 1e6 for value in vector):
                raise ValueError("Export contains an invalid embedding")
            normalized.append(json.dumps(vector, separators=(",", ":")))
        with self.connect() as db:
            db.execute("DELETE FROM people WHERE person_id=?", (person_id,))
            db.execute("INSERT INTO people(person_id,name,relationship,model_version,updated_at) VALUES(?,?,?,?,?)",
                       (person_id, name, relationship, MODEL_VERSION, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
            db.executemany("INSERT INTO face_templates(person_id,embedding_json,model_version) VALUES(?,?,?)",
                           [(person_id, item, MODEL_VERSION) for item in normalized])

    def gallery(self) -> tuple[dict[str, list[list[float]]], dict[str, dict[str, str]]]:
        with self.connect() as db:
            rows = db.execute("""SELECT p.person_id,p.name,p.relationship,p.model_version,t.embedding_json,t.model_version AS template_version
                               FROM people p JOIN face_templates t USING(person_id) ORDER BY p.person_id,t.template_id""").fetchall()
        gallery: dict[str, list[list[float]]] = defaultdict(list)
        people = {}
        for row in rows:
            if row["model_version"] != MODEL_VERSION or row["template_version"] != MODEL_VERSION:
                continue
            gallery[row["person_id"]].append(json.loads(row["embedding_json"]))
            people[row["person_id"]] = {"name": row["name"], "relationship": row["relationship"]}
        return dict(gallery), people

    def enqueue(self, event_type: str, status: str, response_ms: float | None = None) -> None:
        payload = {"deviceId": DEVICE_ID, "eventType": event_type, "status": status,
                   "responseMs": response_ms, "observedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        with self.connect() as db:
            db.execute("INSERT INTO event_queue(event_id,payload_json,created_at) VALUES(?,?,?)",
                       (uuid.uuid4().hex, json.dumps(payload), payload["observedAt"]))

    def upload_queue(self) -> tuple[int, int]:
        url = os.environ.get("FACE_MEMORY_SYNC_URL", "").rstrip("/")
        token = os.environ.get("FACE_MEMORY_DEVICE_TOKEN", "")
        uploaded = 0
        if url and token:
            with self.connect() as db:
                rows = db.execute("SELECT event_id,payload_json FROM event_queue ORDER BY created_at LIMIT 100").fetchall()
        else:
            rows = []
        for row in rows:
            request = Request(url + "/api/device/events", data=row["payload_json"].encode(), method="POST",
                              headers={"content-type": "application/json", "authorization": f"Bearer {token}"})
            try:
                with urlopen(request, timeout=5) as response:
                    if response.status not in (200, 202):
                        break
                with self.connect() as db:
                    db.execute("DELETE FROM event_queue WHERE event_id=?", (row["event_id"],))
                uploaded += 1
            except (URLError, TimeoutError, OSError):
                with self.connect() as db:
                    db.execute("UPDATE event_queue SET attempts=attempts+1 WHERE event_id=?", (row["event_id"],))
                break
        with self.connect() as db:
            remaining = db.execute("SELECT COUNT(*) FROM event_queue").fetchone()[0]
        return uploaded, int(remaining)


def percentile95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, int((0.95 * len(ordered) + 0.999999999)) - 1)]


def announce(person_id: str, people: dict[str, dict[str, str]], audio_dir: Path, now: float, last: dict[str, float], cooldown: float) -> bool:
    if now - last.get(person_id, -1e9) < cooldown:
        return False
    wav = audio_dir / f"{person_id}.wav"
    if not wav.is_file():
        print(f"No local WAV for {person_id}; create {wav} with caregiver-approved speech.")
        return False
    try:
        subprocess.Popen(["aplay", "-q", str(wav)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        last[person_id] = now
        print(f"ANNOUNCED {people[person_id]['name']} · {people[person_id]['relationship']}")
        return True
    except FileNotFoundError:
        print("`aplay` is unavailable; install alsa-utils and check the 3.5 mm output.")
        return False


def run_frame(frame, encoder, matcher, gallery, people, audio_dir, latencies, last_audio, cooldown):
    start = time.perf_counter()
    try:
        vector = encoder.encode_frame(frame)
        matched = matcher.match(vector, gallery)
        elapsed = (time.perf_counter() - start) * 1000
        if matched.status == "identified" and matched.person_id in people:
            pid = str(matched.person_id)
            if announce(pid, people, audio_dir, time.monotonic(), last_audio, cooldown):
                latencies.append(elapsed)
            print(f"known score={matched.score:.3f} margin={matched.score-matched.second_score:.3f} response_ms={elapsed:.1f}")
            return "known", elapsed
        print(f"{matched.status} response_ms={elapsed:.1f}")
        return matched.status, elapsed
    except (NoFaceError, MultipleFacesError) as error:
        print("no_face" if isinstance(error, NoFaceError) else "multiple_faces")
        return "no_face" if isinstance(error, NoFaceError) else "multiple_faces", None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run offline Pi face memory from an image, video, or CSI camera")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path, help="Local test image (one frame)")
    source.add_argument("--video", type=Path, help="Local test video")
    source.add_argument("--camera", action="store_true", help="Use Picamera2 CSI camera")
    parser.add_argument("--import-person", type=Path, action="append", default=[], help="Import one downloaded private person export")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--audio-dir", type=Path, default=AUDIO_DIR)
    parser.add_argument("--scan-interval", type=float, default=1.0)
    parser.add_argument("--cooldown", type=float, default=12.0)
    args = parser.parse_args()
    store = PiStore(args.db)
    for export_path in args.import_person:
        store.import_person(json.loads(export_path.read_text(encoding="utf-8")))
    gallery, people = store.gallery()
    if not gallery:
        print("No compatible face templates are installed. Export a selected person from the website first.", file=sys.stderr)
        return 2
    model_dir = Path(os.environ.get("FACE_MEMORY_MODEL_DIR", ROOT / "face_memory_system/models"))
    encoder = OpenCVFaceEncoder(
        model_dir / "face_detection_yunet_2023mar.onnx",
        model_dir / "face_recognition_sface_2021dec.onnx",
    )
    matcher = IdentityMatcher(IDENTITY_THRESHOLD, MIN_MARGIN)
    store.enqueue("device_status", "online")
    uploaded, pending = store.upload_queue()
    print(f"Device online · {len(people)} selected people · model {MODEL_VERSION} · uploaded={uploaded} queued={pending}")
    latencies: list[float] = []
    last_audio: dict[str, float] = {}
    try:
        if args.image:
            import cv2
            frame = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
            if frame is None:
                raise FileNotFoundError(f"Cannot read image {args.image}")
            status, response = run_frame(frame, encoder, matcher, gallery, people, args.audio_dir, latencies, last_audio, args.cooldown)
            store.enqueue("recognition", status, response)
        elif args.video:
            import cv2
            capture = cv2.VideoCapture(str(args.video))
            if not capture.isOpened():
                raise FileNotFoundError(f"Cannot open video {args.video}")
            try:
                while True:
                    started = time.monotonic()
                    ok, frame = capture.read()
                    if not ok:
                        break
                    status, response = run_frame(frame, encoder, matcher, gallery, people, args.audio_dir, latencies, last_audio, args.cooldown)
                    store.enqueue("recognition", status, response)
                    store.upload_queue()
                    time.sleep(max(0.0, args.scan_interval - (time.monotonic() - started)))
            finally:
                capture.release()
        else:
            from picamera2 import Picamera2
            import cv2
            camera = Picamera2()
            camera.configure(camera.create_video_configuration(main={"size": (640, 480), "format": "RGB888"}))
            camera.start()
            try:
                while True:
                    started = time.monotonic()
                    rgb = camera.capture_array()
                    status, response = run_frame(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), encoder, matcher, gallery, people,
                                                 args.audio_dir, latencies, last_audio, args.cooldown)
                    if response is not None:
                        store.enqueue("recognition", status, response)
                    store.upload_queue()
                    time.sleep(max(0.0, args.scan_interval - (time.monotonic() - started)))
            except KeyboardInterrupt:
                pass
            finally:
                camera.stop()
    except KeyboardInterrupt:
        pass
    print("Pi hardware status: PENDING — test this flow on the Raspberry Pi 2 before reporting hardware results.")
    print(json.dumps({"spoken_response_count": len(latencies), "latency_max_ms": max(latencies) if latencies else None,
                      "latency_p95_ms": percentile95(latencies), "measurement_status": "pending_pi2_hardware_test"}, indent=2))
    uploaded, pending = store.upload_queue()
    print(f"Event sync: uploaded={uploaded}, queued={pending}; queued events contain status and timing only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
