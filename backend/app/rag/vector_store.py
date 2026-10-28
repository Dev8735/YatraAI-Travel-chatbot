"""Qdrant wrapper. Uses a Qdrant server when QDRANT_URL is set, else embedded local storage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qm

from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class VectorHit:
    chunk_id: str
    score: float
    payload: dict[str, Any]


class VectorStore:
    def __init__(self, client: AsyncQdrantClient, base_collection: str, embedder_name: str, dim: int) -> None:
        self.client = client
        # One collection per embedder so switching models never mixes vector spaces.
        self.collection = f"{base_collection}__{embedder_name}".replace("/", "_")
        self.dim = dim

    @classmethod
    def connect(cls, *, url: str | None, api_key: str | None, path: str, base_collection: str,
                embedder_name: str, dim: int) -> VectorStore:
        if url:
            client = AsyncQdrantClient(url=url, api_key=api_key, timeout=30)
        elif path == ":memory:":
            client = AsyncQdrantClient(location=":memory:")
        else:
            client = AsyncQdrantClient(path=path)
        return cls(client, base_collection, embedder_name, dim)

    async def ensure_collection(self) -> None:
        if not await self.client.collection_exists(self.collection):
            await self.client.create_collection(
                self.collection,
                vectors_config=qm.VectorParams(size=self.dim, distance=qm.Distance.COSINE),
            )
            for field in ("source_id", "document_id"):
                try:
                    await self.client.create_payload_index(self.collection, field, qm.PayloadSchemaType.KEYWORD)
                except Exception:  # local mode does not support payload indexes
                    pass

    async def count(self) -> int:
        result = await self.client.count(self.collection, exact=True)
        return result.count

    async def upsert(self, ids: list[str], vectors: list[list[float]], payloads: list[dict[str, Any]]) -> None:
        if not ids:
            return
        points = [qm.PointStruct(id=i, vector=v, payload=p) for i, v, p in zip(ids, vectors, payloads, strict=True)]
        for start in range(0, len(points), 128):
            await self.client.upsert(self.collection, points=points[start:start + 128], wait=True)

    async def delete_by(self, field: str, value: str) -> None:
        await self.client.delete(
            self.collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(must=[qm.FieldCondition(key=field, match=qm.MatchValue(value=value))])
            ),
            wait=True,
        )

    async def search(self, vector: list[float], limit: int, source_ids: list[str] | None = None) -> list[VectorHit]:
        query_filter = None
        if source_ids:
            query_filter = qm.Filter(must=[qm.FieldCondition(key="source_id", match=qm.MatchAny(any=source_ids))])
        response = await self.client.query_points(
            self.collection, query=vector, limit=limit, query_filter=query_filter, with_payload=True
        )
        return [VectorHit(str(p.id), float(p.score), p.payload or {}) for p in response.points]

    async def health(self) -> bool:
        try:
            await self.client.get_collections()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self.client.close()
