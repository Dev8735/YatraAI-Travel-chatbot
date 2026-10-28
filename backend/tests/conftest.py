"""Shared fixtures: an isolated app (temp SQLite, in-memory Qdrant, hashing embedder, demo LLM)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.core.rate_limit import limiter
from app.llm.base import DemoLLM
from app.main import create_app
from app.rag.embeddings import HashingEmbedder
from app.services.container import build_container

PUBLIC_IP = "93.184.216.34"


async def fake_resolver(host: str, port: int) -> list[str]:
    table = {"evil.example": ["127.0.0.1"], "mixed.example": [PUBLIC_IP, "10.0.0.5"],
             "metadata.example": ["169.254.169.254"]}
    return table.get(host, [PUBLIC_IP])


def make_settings(tmp_path: Path, **overrides) -> Settings:
    base = dict(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
        qdrant_url=None,
        qdrant_path=":memory:",
        embedding_backend="hashing",
        llm_provider="demo",
        places_provider="demo",
        routes_provider="none",
        google_maps_api_key=None,
        anthropic_api_key=None,
        openai_api_key=None,
        ollama_base_url=None,
        crawl_delay_seconds=0,
        seed_demo_data=True,
        log_level="WARNING",
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def container_overrides() -> dict:
    """Tests can override container parts (llm, places, routes, fetcher_factory)."""
    return {}


@pytest.fixture
async def app_and_client(settings: Settings, container_overrides: dict) -> AsyncIterator[tuple]:
    limiter.reset()

    def factory(s, sessions):  # noqa: ANN001
        c = build_container(s, sessions, embedder=HashingEmbedder(s.hashing_dim),
                            llm=container_overrides.get("llm", DemoLLM()),
                            places=container_overrides.get("places"), routes=container_overrides.get("routes"),
                            fetcher_factory=container_overrides.get("fetcher_factory"))
        c.resolver = fake_resolver
        return c

    app = create_app(settings, container_factory=factory)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield app, client


@pytest.fixture
async def client(app_and_client) -> httpx.AsyncClient:  # noqa: ANN001
    return app_and_client[1]


@pytest.fixture
def container(app_and_client):  # noqa: ANN001
    return app_and_client[0].state.container


CLIENT_A = {"X-Client-Id": "client-aaaa-0001"}
CLIENT_B = {"X-Client-Id": "client-bbbb-0002"}
