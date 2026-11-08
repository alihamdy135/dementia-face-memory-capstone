from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from .core import IdentityMatcher
from .store import MemoryStore
from .settings import IDENTITY_THRESHOLD, MIN_MARGIN


class FaceEncoder(Protocol):
    def encode_image(self, image_path: str | Path) -> Sequence[float]: ...


class FaceMemoryService:
    """Connect a fixed face encoder to dynamic local enrollment and profile memory."""

    def __init__(
        self,
        encoder: FaceEncoder,
        store: MemoryStore,
        threshold: float | None = IDENTITY_THRESHOLD,
        min_margin: float = MIN_MARGIN,
    ) -> None:
        self.encoder = encoder
        self.store = store
        self.matcher = (
            IdentityMatcher(threshold=threshold, min_margin=min_margin)
            if threshold is not None
            else None
        )

    def enroll_image(
        self,
        image_path: str | Path,
        person_id: str,
        display_name: str,
        relationship: str,
    ) -> dict[str, str]:
        embedding = self.encoder.encode_image(image_path)
        self.store.add_person(person_id, display_name, relationship)
        self.store.add_template(person_id, embedding, str(image_path))
        profile = self.store.get_person(person_id)
        if profile is None:
            raise RuntimeError("Profile was not persisted after enrollment")
        return profile

    def recognize_image(self, image_path: str | Path) -> dict[str, object]:
        if self.matcher is None:
            raise RuntimeError("Recognition is disabled until a validation threshold is calibrated")
        embedding = self.encoder.encode_image(image_path)
        result = self.matcher.match(embedding, self.store.get_gallery())
        payload: dict[str, object] = {
            "status": result.status,
            "person_id": result.person_id,
            "score": result.score,
            "second_score": result.second_score,
            "person": None,
            "memories": [],
        }
        if result.person_id is not None:
            payload["person"] = self.store.get_person(result.person_id)
            payload["memories"] = self.store.get_memories(result.person_id)
        return payload

    def add_memory(
        self,
        person_id: str,
        content: str,
        audio_path: str | None = None,
        source: str = "caregiver",
    ) -> None:
        self.store.add_memory(person_id, content, audio_path, source)
