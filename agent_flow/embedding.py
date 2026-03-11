"""
embedding.py — Shared sentence-embedding singleton for Phase 3.

Loads the model once and exposes encode() for all agents.
Falls back gracefully if sentence-transformers is not installed.
"""

import math
import numpy as np
from config.config import EMBEDDING_MODEL, RECENCY_DECAY


# ── Singleton holder ─────────────────────────────────────────
_embed_model = None
_model_available: bool | None = None   # None = not yet checked


def get_embed_model():
    """
    Return the shared SentenceTransformer instance (lazy-loaded).

    Returns None if the library is missing or the model fails to load.
    """
    global _embed_model, _model_available

    if _model_available is False:
        return None           # already tried and failed

    if _embed_model is not None:
        return _embed_model   # already loaded

    try:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer(EMBEDDING_MODEL)
        _model_available = True
        print(f"  [Embedding] Loaded model: {EMBEDDING_MODEL}")
        return _embed_model
    except Exception as e:
        _model_available = False
        print(f"  [Embedding] sentence-transformers unavailable — "
              f"falling back to heuristic retrieval.  ({e})")
        return None


def embed_text(text: str) -> np.ndarray | None:
    """
    Encode a single string into a 384-dim float32 vector.

    Returns None if the model is unavailable.
    """
    model = get_embed_model()
    if model is None:
        return None
    return model.encode(text, convert_to_numpy=True)


# ── Scoring utilities ────────────────────────────────────────

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors, clamped to [0, 1]."""
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    sim = float(dot / norm)
    return max(0.0, min(1.0, sim))


def recency_score(current_round: int, node_round: int) -> float:
    """Exponential recency decay: same round = 1.0, older rounds → 0."""
    gap = max(0, current_round - node_round)
    return math.exp(-RECENCY_DECAY * gap)
