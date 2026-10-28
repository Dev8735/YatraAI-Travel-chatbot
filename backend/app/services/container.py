"""Process-wide singletons (embedder, vector store, providers) wired from settings."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.ingestion.fetcher import SafeFetcher
from app.ingestion.url_safety import Resolver, system_resolver
from app.llm.base import LLMProvider
from app.llm.providers import build_llm
from app.providers.places.base import PlacesProvider
from app.providers.places.demo import DemoPlacesProvider
from app.providers.places.google import GooglePlacesProvider
from app.providers.routes.providers import GoogleRoutesProvider, NoRoutesProvider, RoutesProvider
from app.providers.transport.providers import NoTransportProvider, TransportProvider
from app.rag.embeddings import Embedder, build_embedder
from app.rag.retriever import CorpusVersion, HybridRetriever
from app.rag.vector_store import VectorStore


@dataclass
class Container:
    settings: Settings
    sessions: async_sessionmaker[AsyncSession]
    embedder: Embedder
    store: VectorStore
    retriever: HybridRetriever
    corpus_version: CorpusVersion
    llm: LLMProvider
    places: PlacesProvider
    routes: RoutesProvider
    transport: TransportProvider
    fetcher_factory: Callable[[], SafeFetcher]
    resolver: Resolver = system_resolver
    tasks: set[asyncio.Task] = field(default_factory=set)

    def spawn(self, coro) -> asyncio.Task:  # noqa: ANN001
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def close(self) -> None:
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        for provider in (self.places, self.routes):
            closer = getattr(provider, "aclose", None)
            if closer:
                await closer()
        await self.store.close()


def build_container(settings: Settings, sessions: async_sessionmaker[AsyncSession], *,
                    embedder: Embedder | None = None, llm: LLMProvider | None = None,
                    places: PlacesProvider | None = None, routes: RoutesProvider | None = None,
                    fetcher_factory: Callable[[], SafeFetcher] | None = None) -> Container:
    embedder = embedder or build_embedder(settings.embedding_backend, settings.embedding_model, settings.hashing_dim)
    store = VectorStore.connect(url=settings.qdrant_url, api_key=settings.qdrant_api_key, path=settings.qdrant_path,
                                base_collection=settings.qdrant_collection, embedder_name=embedder.name,
                                dim=embedder.dim)
    corpus_version = CorpusVersion()
    retriever = HybridRetriever(embedder, store, sessions, corpus_version)

    if places is None:
        use_google = settings.places_provider == "google" or (
            settings.places_provider == "auto" and settings.google_maps_api_key)
        places = (GooglePlacesProvider(settings.google_maps_api_key, settings.google_places_language)
                  if use_google and settings.google_maps_api_key else DemoPlacesProvider())
    if routes is None:
        use_google = settings.routes_provider == "google" or (
            settings.routes_provider == "auto" and settings.google_maps_api_key)
        routes = GoogleRoutesProvider(settings.google_maps_api_key) if use_google and settings.google_maps_api_key \
            else NoRoutesProvider()

    def default_fetcher() -> SafeFetcher:
        return SafeFetcher(user_agent=settings.crawler_user_agent, timeout=settings.crawl_timeout_seconds,
                           max_bytes=settings.crawl_max_bytes, max_redirects=settings.crawl_max_redirects,
                           allow_private=settings.crawl_allow_private_networks)

    return Container(
        settings=settings, sessions=sessions, embedder=embedder, store=store, retriever=retriever,
        corpus_version=corpus_version, llm=llm or build_llm(settings), places=places, routes=routes,
        transport=NoTransportProvider(), fetcher_factory=fetcher_factory or default_fetcher,
    )


def get_container(request: Request) -> Container:
    return request.app.state.container
