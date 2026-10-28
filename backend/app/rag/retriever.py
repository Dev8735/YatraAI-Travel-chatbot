"""Hybrid retrieval: dense vectors (Qdrant) + BM25 keywords, fused with Reciprocal Rank Fusion.

A chunk is marked ``supporting`` only if it clears an evidence bar: its cosine similarity
exceeds the embedder's calibrated threshold, or it contains most of the query's content
terms. Answers are generated only from supporting chunks; if none exist the assistant
says the indexed sources do not cover the question.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Chunk, Document, Source
from app.rag.embeddings import Embedder
from app.rag.keyword import BM25Index, content_terms
from app.rag.vector_store import VectorStore

RRF_K = 60


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    source_id: str
    url: str
    title: str
    heading: str | None
    text: str
    fetched_at: datetime | None
    published_at: str | None
    is_demo: bool
    vector_score: float | None = None
    keyword_score: float | None = None
    keyword_coverage: float = 0.0
    fused_score: float = 0.0
    supporting: bool = False


class CorpusVersion:
    """Bumped whenever chunks are added/removed so the BM25 index knows to rebuild."""

    def __init__(self) -> None:
        self.value = 0

    def bump(self) -> None:
        self.value += 1


class HybridRetriever:
    def __init__(self, embedder: Embedder, store: VectorStore, sessions: async_sessionmaker[AsyncSession],
                 corpus_version: CorpusVersion, *, min_vector_score: float | None = None) -> None:
        self.embedder = embedder
        self.store = store
        self.sessions = sessions
        self.corpus_version = corpus_version
        self.bm25 = BM25Index()
        self.min_vector_score = min_vector_score if min_vector_score is not None else embedder.evidence_threshold

    async def _ensure_bm25(self, session: AsyncSession) -> None:
        if self.bm25.version == self.corpus_version.value:
            return
        rows = (await session.execute(select(Chunk.id, Chunk.source_id, Chunk.heading, Chunk.text, Document.title)
                                      .join(Document, Chunk.document_id == Document.id))).all()
        # Page title + heading are indexed with the text so "sunset in Udaipur" matches the Udaipur page's
        # sunset passage even though the passage itself never repeats the city name.
        self.bm25.build([(r.id, r.source_id, f"{r.title} {r.heading or ''} {r.text}") for r in rows],
                        self.corpus_version.value)

    async def retrieve(self, query: str, *, top_k: int = 6,
                       source_ids: list[str] | None = None) -> list[RetrievedChunk]:
        if not query.strip():
            return []
        pool = max(top_k * 3, 12)
        vector = await self.embedder.embed_query(query)
        vector_hits = await self.store.search(vector, pool, source_ids)
        async with self.sessions() as session:
            await self._ensure_bm25(session)
            keyword_hits = self.bm25.search(query, pool, source_ids)

            fused: dict[str, float] = {}
            vscore: dict[str, float] = {}
            kscore: dict[str, tuple[float, float]] = {}
            for rank, hit in enumerate(vector_hits):
                fused[hit.chunk_id] = fused.get(hit.chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
                vscore[hit.chunk_id] = hit.score
            for rank, khit in enumerate(keyword_hits):
                fused[khit.chunk_id] = fused.get(khit.chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
                kscore[khit.chunk_id] = (khit.score, khit.coverage)
            if not fused:
                return []

            rows = (await session.execute(
                select(Chunk, Document, Source.is_demo)
                .join(Document, Chunk.document_id == Document.id)
                .join(Source, Document.source_id == Source.id)
                .where(Chunk.id.in_(list(fused)))
            )).all()

        n_terms = len(set(content_terms(query)))
        results: list[RetrievedChunk] = []
        seen_text: set[str] = set()
        for chunk, doc, is_demo in rows:
            digest = hashlib.sha1(chunk.text.encode("utf-8")).hexdigest()
            if digest in seen_text:  # identical boilerplate chunk on several pages
                continue
            seen_text.add(digest)
            v = vscore.get(chunk.id)
            k, coverage = kscore.get(chunk.id, (None, 0.0))
            matched_terms = round(coverage * n_terms)
            keyword_ok = coverage >= 0.5 and matched_terms >= min(2, n_terms)
            results.append(RetrievedChunk(
                chunk_id=chunk.id, document_id=doc.id, source_id=doc.source_id, url=doc.url,
                title=doc.title, heading=chunk.heading, text=chunk.text, fetched_at=doc.fetched_at,
                published_at=doc.published_at, is_demo=bool(is_demo), vector_score=v, keyword_score=k,
                keyword_coverage=coverage, fused_score=fused[chunk.id],
                supporting=(v is not None and v >= self.min_vector_score) or keyword_ok,
            ))
        # Supporting chunks first, then fused rank; newer fetches win exact ties.
        results.sort(key=lambda r: (r.supporting, r.fused_score,
                                    r.fetched_at.timestamp() if r.fetched_at else 0.0), reverse=True)
        return results[:top_k]
