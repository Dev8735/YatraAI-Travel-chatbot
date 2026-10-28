"""In-memory BM25 keyword index over chunk texts, rebuilt lazily when the corpus changes.

Complements vector search for exact names (forts, ghats, train names) that embedding
models can blur. Fine for tens of thousands of chunks; beyond that use Qdrant sparse
vectors or Postgres full-text search (see README).
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from app.rag.embeddings import tokenize

STOPWORDS = {
    # English
    "a", "an", "the", "is", "are", "was", "were", "be", "to", "of", "in", "on", "at", "for", "and", "or",
    "with", "by", "from", "as", "it", "this", "that", "what", "which", "who", "how", "when", "where",
    "do", "does", "did", "can", "i", "me", "my", "we", "you", "your", "there", "about", "tell", "please",
    "should", "would", "could", "any", "some", "into", "than", "then", "so", "if", "not", "no", "yes",
    # Hinglish / Hindi
    "hai", "hain", "kya", "ka", "ki", "ke", "ko", "mein", "se", "aur", "ya", "batao", "bataiye",
    "है", "हैं", "क्या", "का", "की", "के", "को", "में", "से", "और", "या", "बताओ", "बताइए",
    # Gujarati
    "છે", "શું", "નો", "ની", "નું", "ને", "માં", "થી", "અને", "કે",
}


def content_terms(text: str) -> list[str]:
    return [t for t in tokenize(text) if t not in STOPWORDS and len(t) > 1]


@dataclass
class KeywordHit:
    chunk_id: str
    score: float
    coverage: float  # fraction of distinct query terms present in the chunk


class BM25Index:
    def __init__(self, k1: float = 1.4, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.version = -1
        self._docs: dict[str, Counter[str]] = {}
        self._lengths: dict[str, int] = {}
        self._sources: dict[str, str] = {}
        self._df: Counter[str] = Counter()
        self._avg = 1.0

    def build(self, rows: list[tuple[str, str, str]], version: int) -> None:
        """rows: (chunk_id, source_id, text)"""
        self._docs.clear()
        self._lengths.clear()
        self._sources.clear()
        self._df = Counter()
        for chunk_id, source_id, text in rows:
            terms = Counter(content_terms(text))
            self._docs[chunk_id] = terms
            self._lengths[chunk_id] = sum(terms.values())
            self._sources[chunk_id] = source_id
            self._df.update(terms.keys())
        self._avg = (sum(self._lengths.values()) / len(self._lengths)) if self._lengths else 1.0
        self.version = version

    def search(self, query: str, limit: int, source_ids: list[str] | None = None) -> list[KeywordHit]:
        q_terms = list(dict.fromkeys(content_terms(query)))
        if not q_terms or not self._docs:
            return []
        n = len(self._docs)
        allowed = set(source_ids) if source_ids else None
        hits: list[KeywordHit] = []
        for chunk_id, tf in self._docs.items():
            if allowed is not None and self._sources[chunk_id] not in allowed:
                continue
            score, matched = 0.0, 0
            length = self._lengths[chunk_id] or 1
            for term in q_terms:
                f = tf.get(term)
                if not f:
                    continue
                matched += 1
                idf = math.log(1 + (n - self._df[term] + 0.5) / (self._df[term] + 0.5))
                score += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * length / self._avg))
            if matched:
                hits.append(KeywordHit(chunk_id, score, matched / len(q_terms)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]
