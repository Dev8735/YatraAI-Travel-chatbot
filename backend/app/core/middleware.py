"""Request ID propagation, access logging and request-size limits."""

from __future__ import annotations

import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging import get_logger, request_id_var

log = get_logger("yatra.access")
_SAFE_ID = re.compile(r"^[A-Za-z0-9\-]{8,64}$")
MAX_BODY_BYTES = 256 * 1024


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.perf_counter()
        try:
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
                return JSONResponse(
                    {"error": {"code": "payload_too_large", "message": "Request body is too large.",
                               "details": {}, "request_id": rid}},
                    status_code=413,
                )
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            log.info(
                "request",
                extra={"fields": {
                    "method": request.method,
                    "path": request.url.path,  # path only: query strings may carry user text
                    "status": response.status_code,
                    "ms": round((time.perf_counter() - start) * 1000, 1),
                }},
            )
            return response
        finally:
            request_id_var.reset(token)
