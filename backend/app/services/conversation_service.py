"""Conversation persistence, scoped to a client id (see README: local/demo security model)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models import Conversation, Message
from app.llm.base import ChatTurn


async def create(session: AsyncSession, client_id: str, title: str | None = None) -> Conversation:
    conv = Conversation(client_id=client_id, title=title or "New trip chat", context={})
    session.add(conv)
    await session.commit()
    return conv


async def get_owned(session: AsyncSession, client_id: str, conversation_id: str) -> Conversation:
    conv = await session.get(Conversation, conversation_id)
    # Same 404 whether missing or owned by another client, so ids cannot be probed.
    if conv is None or conv.client_id != client_id:
        raise NotFoundError("Conversation not found.")
    return conv


async def list_for_client(session: AsyncSession, client_id: str, limit: int,
                          offset: int) -> tuple[list[Conversation], int]:
    total = (await session.execute(select(func.count(Conversation.id))
                                   .where(Conversation.client_id == client_id))).scalar_one()
    rows = await session.execute(select(Conversation).where(Conversation.client_id == client_id)
                                 .order_by(Conversation.updated_at.desc()).limit(limit).offset(offset))
    return list(rows.scalars()), total


async def messages(session: AsyncSession, conversation_id: str, limit: int | None = None) -> list[Message]:
    q = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.desc())
    if limit:
        q = q.limit(limit)
    rows = list((await session.execute(q)).scalars())
    rows.reverse()
    return rows


async def recent_history(session: AsyncSession, conversation_id: str, turns: int) -> list[ChatTurn]:
    """Bounded context: last ``turns`` exchanges, each truncated, roles kept strictly alternating."""
    history: list[ChatTurn] = []
    for m in await messages(session, conversation_id, limit=turns * 2):
        if m.role not in ("user", "assistant"):
            continue
        text = m.content if len(m.content) <= 1200 else m.content[:1200] + " …"
        if history and history[-1].role == m.role:
            history[-1] = ChatTurn(m.role, history[-1].content + "\n\n" + text)  # type: ignore[arg-type]
        else:
            history.append(ChatTurn(m.role, text))  # type: ignore[arg-type]
    while history and history[0].role != "user":
        history.pop(0)
    return history
