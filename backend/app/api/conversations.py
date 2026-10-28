from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import client_id
from app.db.session import get_session
from app.schemas.chat import (
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    ConversationUpdate,
    MessageOut,
    Page,
)
from app.services import conversation_service as svc

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _summary(conv) -> ConversationSummary:  # noqa: ANN001
    return ConversationSummary(id=conv.id, title=conv.title, created_at=conv.created_at, updated_at=conv.updated_at)


@router.get("", response_model=Page, summary="List this client's conversations (newest first)")
async def list_conversations(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                             cid: str = Depends(client_id), session: AsyncSession = Depends(get_session)) -> Page:
    rows, total = await svc.list_for_client(session, cid, limit, offset)
    return Page(items=[_summary(r) for r in rows], total=total, limit=limit, offset=offset)


@router.post("", response_model=ConversationSummary, status_code=201)
async def create_conversation(body: ConversationCreate | None = None, cid: str = Depends(client_id),
                              session: AsyncSession = Depends(get_session)) -> ConversationSummary:
    return _summary(await svc.create(session, cid, body.title if body else None))


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: str, cid: str = Depends(client_id),
                           session: AsyncSession = Depends(get_session)) -> ConversationDetail:
    conv = await svc.get_owned(session, cid, conversation_id)
    msgs = await svc.messages(session, conv.id)
    context = {k: v for k, v in (conv.context or {}).items() if k in ("entities", "itinerary_id", "last_intent")}
    return ConversationDetail(
        **_summary(conv).model_dump(), context=context,
        messages=[MessageOut(id=m.id, role=m.role, content=m.content, created_at=m.created_at,  # type: ignore[arg-type]
                             metadata=m.meta or {}) for m in msgs],
    )


@router.patch("/{conversation_id}", response_model=ConversationSummary, summary="Rename a conversation")
async def rename_conversation(conversation_id: str, body: ConversationUpdate, cid: str = Depends(client_id),
                              session: AsyncSession = Depends(get_session)) -> ConversationSummary:
    conv = await svc.get_owned(session, cid, conversation_id)
    conv.title = body.title.strip()
    await session.commit()
    return _summary(conv)


@router.delete("/{conversation_id}", status_code=204, response_class=Response)
async def delete_conversation(conversation_id: str, cid: str = Depends(client_id),
                              session: AsyncSession = Depends(get_session)) -> Response:
    conv = await svc.get_owned(session, cid, conversation_id)
    await session.delete(conv)
    await session.commit()
    return Response(status_code=204)
