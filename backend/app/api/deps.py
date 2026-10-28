"""Shared request dependencies."""

from __future__ import annotations

import re

from fastapi import Header

from app.core.errors import AppError

_CLIENT_ID = re.compile(r"^[A-Za-z0-9\-]{8,64}$")


async def client_id(x_client_id: str | None = Header(default=None, alias="X-Client-Id")) -> str:
    """Anonymous browser-generated id that scopes conversations and itineraries.

    This is NOT authentication: anyone who knows an id can act as that client. See the
    README's security model before exposing the app publicly.
    """
    if not x_client_id or not _CLIENT_ID.match(x_client_id):
        raise AppError("Missing or invalid X-Client-Id header.", code="client_id_required", status_code=400)
    return x_client_id
