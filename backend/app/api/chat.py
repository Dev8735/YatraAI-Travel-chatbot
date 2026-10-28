from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.api.deps import client_id
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.rate_limit import rate_limit
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import run_chat
from app.services.container import Container, get_container

log = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])
chat_limit = rate_limit("chat", lambda: get_settings().rate_limit_chat_per_minute, 60)


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(chat_limit)],
             summary="Send a message and receive a structured, grounded response")
async def chat(body: ChatRequest, cid: str = Depends(client_id), c: Container = Depends(get_container)) -> ChatResponse:
    async with c.sessions() as session:
        final: ChatResponse | None = None
        async for kind, payload in run_chat(c, session, cid, body.message, body.conversation_id, body.source_ids):
            if kind == "final":
                final = payload
        assert final is not None
        return final


@router.post("/chat/stream", dependencies=[Depends(chat_limit)],
             summary="Same as /api/chat but streamed as Server-Sent Events (meta, delta…, final | error)")
async def chat_stream(body: ChatRequest, cid: str = Depends(client_id), c: Container = Depends(get_container)):
    async def events() -> AsyncIterator[dict]:
        # The DB session lives inside the generator so it stays open for the whole stream.
        async with c.sessions() as session:
            try:
                async for kind, payload in run_chat(c, session, cid, body.message, body.conversation_id,
                                                    body.source_ids):
                    if kind == "final":
                        data = payload.model_dump_json()
                    elif kind == "delta":
                        data = json.dumps({"text": payload}, ensure_ascii=False)
                    else:
                        data = json.dumps(payload, ensure_ascii=False)
                    yield {"event": kind, "data": data}
            except AppError as exc:
                yield {"event": "error", "data": json.dumps({"code": exc.code, "message": exc.message})}
            except Exception:
                log.exception("chat stream failed")
                yield {"event": "error", "data": json.dumps({"code": "internal_error",
                                                             "message": "Something went wrong. Please try again."})}

    return EventSourceResponse(events(), ping=15)
