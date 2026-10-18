import hashlib
import json
import logging
import math
import random
import time
from pathlib import Path
from typing import List

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

CACHE_FILE = Path(__file__).resolve().parent / "seed" / "embeddings_cache.json"
_cache: dict[str, list[float]] | None = None


def _get_cache() -> dict[str, list[float]]:
    global _cache
    if _cache is None:
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    _cache = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load embedding cache: {e}")
                _cache = {}
        else:
            _cache = {}
    return _cache


def _save_cache() -> None:
    global _cache
    if _cache is not None:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f)


def l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


def _deterministic_offline_vector(text: str, dim: int) -> list[float]:
    """Generates a normalized deterministic hash-based vector for test-only use when no API key is set."""
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    raw = [rng.gauss(0, 1) for _ in range(dim)]
    return l2_normalize(raw)


def embed_texts(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """
    Generates normalized 768-d embeddings for a list of texts.
    Uses cached vectors when available, batches API requests up to 50 texts,
    and applies exponential backoff for 429 / 5xx errors.
    Falls back to deterministic offline vectors if GEMINI_API_KEY is empty.
    """
    if not texts:
        return []

    dim = settings.EMBED_DIM
    model = settings.GEMINI_EMBED_MODEL

    # Check for offline fallback
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is absent. Using deterministic test-only offline embeddings.")
        return [_deterministic_offline_vector(t, dim) for t in texts]

    cache = _get_cache()
    results: list[list[float] | None] = [None] * len(texts)
    missing_indices: list[int] = []
    missing_texts: list[str] = []

    # Check cache first
    for idx, text in enumerate(texts):
        key = hashlib.sha256(f"{model}:{task_type}:{text}".encode("utf-8")).hexdigest()
        if key in cache:
            results[idx] = cache[key]
        else:
            missing_indices.append(idx)
            missing_texts.append(text)

    # If all found in cache, return immediately
    if not missing_texts:
        return [r for r in results if r is not None]

    # Process missing in batches of up to 50
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    batch_size = 50
    cache_dirty = False

    for batch_start in range(0, len(missing_texts), batch_size):
        batch = missing_texts[batch_start:batch_start + batch_size]
        indices = missing_indices[batch_start:batch_start + batch_size]

        attempts = 0
        backoff = 1.0
        while attempts < 4:
            try:
                resp = client.models.embed_content(
                    model=model,
                    contents=batch,
                    config=types.EmbedContentConfig(
                        output_dimensionality=dim,
                        task_type=task_type,
                    ),
                )

                if hasattr(resp, "embeddings") and resp.embeddings:
                    vectors = [l2_normalize(e.values) for e in resp.embeddings]
                elif hasattr(resp, "embedding") and resp.embedding:
                    vectors = [l2_normalize(resp.embedding.values)]
                else:
                    raise ValueError(f"Unexpected response structure from embed_content: {resp}")

                for i, text, vec in zip(indices, batch, vectors):
                    results[i] = vec
                    key = hashlib.sha256(f"{model}:{task_type}:{text}".encode("utf-8")).hexdigest()
                    cache[key] = vec
                    cache_dirty = True
                break
            except Exception as e:
                err_str = str(e).lower()
                is_retryable = "429" in err_str or "500" in err_str or "503" in err_str or "quota" in err_str or "resourceexhausted" in err_str
                attempts += 1
                if is_retryable and attempts < 4:
                    logger.warning(f"Embedding request failed with {e}. Retrying in {backoff}s (attempt {attempts}/4)...")
                    time.sleep(backoff)
                    backoff *= 2.0
                else:
                    raise e

    if cache_dirty:
        _save_cache()

    return [r for r in results if r is not None]
