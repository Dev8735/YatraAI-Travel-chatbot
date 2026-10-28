"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, conversations, health, knowledge, travel
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.db.migrate import upgrade_head_async
from app.db.session import dispose_engine, init_engine, session_factory
from app.services import knowledge_service as ks
from app.services.container import Container, build_container

log = get_logger("yatra")


def create_app(settings: Settings | None = None, *, container_factory=None) -> FastAPI:  # noqa: ANN001
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await upgrade_head_async(settings.database_url)
        init_engine(settings.database_url)
        container: Container = (container_factory or build_container)(settings, session_factory())
        app.state.container = container
        await container.store.ensure_collection()
        await ks.fail_interrupted_jobs(container)
        await ks.reindex_vectors_if_missing(container)
        if settings.seed_demo_data:
            await ks.seed_demo_corpus(container)
        log.info("startup complete", extra={"fields": {
            "llm": container.llm.name, "places": container.places.name, "routes": container.routes.name,
            "embeddings": container.embedder.name, "db": "sqlite" if settings.is_sqlite else "postgresql"}})
        try:
            yield
        finally:
            await container.close()
            await dispose_engine()

    app = FastAPI(
        title="YatraAI API",
        version="0.1.0",
        description="Grounded travel assistant: website RAG with citations, places, routes and itineraries.",
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Client-Id", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        allow_credentials=False,
    )
    install_error_handlers(app)
    for module in (health, chat, conversations, knowledge, travel):
        app.include_router(module.router)
    return app


app = create_app()
