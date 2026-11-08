from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
from typing import Iterator, Sequence


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_embedding(embedding: Sequence[float]) -> list[float]:
    values = [float(value) for value in embedding]
    if not values or any(not math.isfinite(value) for value in values):
        raise ValueError("Embedding must contain finite numeric values")
    if math.fsum(value * value for value in values) == 0.0:
        raise ValueError("Embedding must not be a zero vector")
    return values


class MemoryStore:
    """Local SQLite storage for profiles, face templates, and caregiver notes."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS people (
                    person_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    relationship TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS face_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_id TEXT NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
                    embedding_json TEXT NOT NULL,
                    source_path TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memories (
                    memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_id TEXT NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    audio_path TEXT,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_templates_person ON face_templates(person_id);
                CREATE INDEX IF NOT EXISTS idx_memories_person ON memories(person_id, created_at);
                """
            )

    def add_person(self, person_id: str, display_name: str, relationship: str) -> None:
        person_id = person_id.strip()
        display_name = display_name.strip()
        relationship = relationship.strip()
        if not person_id or not display_name or not relationship:
            raise ValueError("person_id, display_name, and relationship are required")
        now = _timestamp()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO people(person_id, display_name, relationship, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(person_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    relationship = excluded.relationship,
                    updated_at = excluded.updated_at
                """,
                (person_id, display_name, relationship, now, now),
            )

    def add_template(
        self,
        person_id: str,
        embedding: Sequence[float],
        source_path: str | None = None,
    ) -> None:
        values = _validate_embedding(embedding)
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM people WHERE person_id = ?", (person_id,)
            ).fetchone()
            if exists is None:
                raise ValueError(f"Unknown person_id: {person_id}")
            connection.execute(
                "INSERT INTO face_templates(person_id, embedding_json, source_path, created_at) VALUES (?, ?, ?, ?)",
                (person_id, json.dumps(values), source_path, _timestamp()),
            )

    def add_memory(
        self,
        person_id: str,
        content: str,
        audio_path: str | None = None,
        source: str = "caregiver",
    ) -> None:
        content = content.strip()
        if not content and not audio_path:
            raise ValueError("Provide note text or an audio_path")
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM people WHERE person_id = ?", (person_id,)
            ).fetchone()
            if exists is None:
                raise ValueError(f"Unknown person_id: {person_id}")
            connection.execute(
                "INSERT INTO memories(person_id, content, audio_path, source, created_at) VALUES (?, ?, ?, ?, ?)",
                (person_id, content, audio_path, source, _timestamp()),
            )

    def get_person(self, person_id: str) -> dict[str, str] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT person_id, display_name, relationship, created_at, updated_at FROM people WHERE person_id = ?",
                (person_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_gallery(self) -> dict[str, list[list[float]]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT person_id, embedding_json FROM face_templates ORDER BY template_id"
            ).fetchall()
        gallery: dict[str, list[list[float]]] = {}
        for row in rows:
            gallery.setdefault(row["person_id"], []).append(json.loads(row["embedding_json"]))
        return gallery

    def get_memories(self, person_id: str) -> list[dict[str, str | None]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT content, audio_path, source, created_at FROM memories WHERE person_id = ? ORDER BY created_at",
                (person_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_person(self, person_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM people WHERE person_id = ?", (person_id,))
        return cursor.rowcount > 0
