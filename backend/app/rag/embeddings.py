"""Embedding backends.

* SentenceTransformerEmbedder — `paraphrase-multilingual-MiniLM-L12-v2` (384-d). Trained on
  parallel data for 50+ languages including Hindi (hi) and Gujarati (gu), so a Hindi
  question can retrieve an English passage. Small enough for CPU. Requires
  requirements-ml.txt (PyTorch).
* HashingEmbedder — deterministic signed feature hashing of words and character n-grams.
  No model download, script-agnostic, but purely lexical: it cannot match a Hindi
  question to an English passage. Used for tests and when PyTorch is not installed.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import re
from typing import Protocol

from app.core.logging import get_logger

log = get_logger(__name__)
TOKEN_RE = re.compile(r"[\wऀ-ॿ઀-૿]+", re.UNICODE)


class Embedder(Protocol):
    name: str
    dim: int
    # Cosine score above which a chunk counts as supporting evidence (calibrated per model).
    evidence_threshold: float

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


class HashingEmbedder:
    # Lexical vectors are weakly discriminative (see eval), so on their own they only count as
    # evidence at high similarity; the retriever's keyword-coverage test does most of the gating.
    evidence_threshold = 0.45

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim
        self.name = f"hashing-{dim}"

    def _features(self, text: str) -> dict[int, float]:
        feats: dict[int, float] = {}
        tokens = tokenize(text)

        def add(feature: str, weight: float) -> None:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "little")
            idx = value % self.dim
            sign = 1.0 if (value >> 63) & 1 else -1.0
            feats[idx] = feats.get(idx, 0.0) + sign * weight

        for tok in tokens:
            add("w:" + tok, 1.0)
            padded = f"<{tok}>"
            if len(tok) > 3:
                for n in (3, 4):
                    for i in range(len(padded) - n + 1):
                        add(f"c{n}:" + padded[i:i + n], 0.35)
        for a, b in zip(tokens, tokens[1:], strict=False):
            add(f"b:{a}_{b}", 0.5)
        return feats

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for idx, val in self._features(text).items():
            vec[idx] = val
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class SentenceTransformerEmbedder:
    evidence_threshold = 0.35

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # heavy import, kept lazy

        self._model = SentenceTransformer(model_name, device="cpu")
        self.dim = int(self._model.get_sentence_embedding_dimension())
        short = model_name.rsplit("/", 1)[-1]
        self.name = f"st-{short}"

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, batch_size=32, normalize_embeddings=True,
                                     show_progress_bar=False)
        return [v.tolist() for v in vectors]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._encode, texts)

    async def embed_query(self, text: str) -> list[float]:
        return (await asyncio.to_thread(self._encode, [text]))[0]


def build_embedder(backend: str, model_name: str, hashing_dim: int) -> Embedder:
    if backend in ("auto", "sentence_transformers"):
        try:
            embedder = SentenceTransformerEmbedder(model_name)
            log.info("embeddings: using %s", embedder.name)
            return embedder
        except Exception as exc:  # ImportError, or model download failure
            if backend == "sentence_transformers":
                raise RuntimeError(
                    "EMBEDDING_BACKEND=sentence_transformers but the model could not be loaded. "
                    "Install backend/requirements-ml.txt and check network access for the first download."
                ) from exc
            log.warning("embeddings: sentence-transformers unavailable (%s); using hashing fallback",
                        type(exc).__name__)
    return HashingEmbedder(hashing_dim)
