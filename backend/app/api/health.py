from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.services.container import Container, get_container

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service and dependency health, plus which features are live vs demo")
async def health(c: Container = Depends(get_container)) -> dict:
    db_ok = True
    try:
        async with c.sessions() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    vector_ok = await c.store.health()
    components = {
        "database": {"ok": db_ok, "engine": "sqlite" if c.settings.is_sqlite else "postgresql"},
        "vector_store": {"ok": vector_ok, "mode": "server" if c.settings.qdrant_url else "embedded",
                         "collection": c.store.collection},
        "embeddings": {"name": c.embedder.name, "dim": c.embedder.dim,
                       "multilingual": c.embedder.name.startswith("st-")},
        "llm": {"provider": c.llm.name, "model": c.llm.model, "live": c.llm.is_live},
        "places": {"provider": c.places.name, "live": c.places.is_live},
        "routes": {"provider": c.routes.name, "live": c.routes.is_live},
        "transport": {"provider": c.transport.name, "live": c.transport.is_live},
    }
    demo_mode = not (c.llm.is_live and c.places.is_live and c.routes.is_live)
    return {
        "status": "ok" if db_ok and vector_ok else "degraded",
        "environment": c.settings.app_env,
        "demo_mode": demo_mode,
        "components": components,
    }
