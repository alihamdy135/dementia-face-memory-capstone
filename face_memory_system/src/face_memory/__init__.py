"""Offline face recognition and memory storage prototype."""

from .core import IdentityMatcher, MatchResult, cosine_similarity
from .store import MemoryStore

__all__ = ["IdentityMatcher", "MatchResult", "MemoryStore", "cosine_similarity"]
