"""SSRF-safe HTTP fetcher.

Every hop (initial request and each redirect) is re-validated, and the TCP connection
goes to the IP address that was validated, with the original hostname used for the
Host header and TLS SNI/certificate verification. Responses are size-capped and
never executed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from app.core.errors import UnsafeURLError
from app.ingestion.url_safety import Resolver, ValidatedURL, system_resolver, validate_public_url

HTML_TYPES = ("text/html", "application/xhtml+xml")
TEXT_TYPES = ("text/plain",)


class FetchError(Exception):
    """A user-safe description of why a page could not be fetched."""


@dataclass
class FetchResult:
    url: str  # final URL after redirects
    status_code: int
    content_type: str
    text: str
    headers: dict[str, str] = field(default_factory=dict)


_CHARSET_RE = re.compile(r"charset=([\w\-]+)", re.IGNORECASE)
_META_CHARSET_RE = re.compile(rb"<meta[^>]+charset=[\"']?([\w\-]+)", re.IGNORECASE)


def _decode(body: bytes, content_type: str) -> str:
    candidates = []
    m = _CHARSET_RE.search(content_type)
    if m:
        candidates.append(m.group(1))
    m2 = _META_CHARSET_RE.search(body[:4096])
    if m2:
        candidates.append(m2.group(1).decode("ascii", "ignore"))
    candidates.append("utf-8")
    for enc in candidates:
        try:
            return body.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


def _pinned_url(target: ValidatedURL, ip: str) -> str:
    parts = urlsplit(target.url)
    host = f"[{ip}]" if ":" in ip else ip
    default = 443 if target.scheme == "https" else 80
    netloc = host if target.port == default else f"{host}:{target.port}"
    return urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))


class SafeFetcher:
    def __init__(
        self,
        *,
        user_agent: str,
        timeout: float = 15.0,
        max_bytes: int = 2_000_000,
        max_redirects: int = 5,
        resolver: Resolver = system_resolver,
        allow_private: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.resolver = resolver
        self.allow_private = allow_private
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
            follow_redirects=False,
            trust_env=False,  # ignore proxy env vars; they could route around the checks
            transport=transport,
            headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> SafeFetcher:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def fetch(self, url: str, *, accept: tuple[str, ...] = HTML_TYPES + TEXT_TYPES) -> FetchResult:
        current = url
        for _hop in range(self.max_redirects + 1):
            try:
                target = await validate_public_url(current, resolver=self.resolver,
                                                   allow_private=self.allow_private)
            except UnsafeURLError as exc:
                raise FetchError(exc.message) from exc

            ip = target.addresses[0]
            request = self._client.build_request(
                "GET",
                _pinned_url(target, ip),
                headers={"Host": urlsplit(target.url).netloc},
                extensions={"sni_hostname": target.host} if target.scheme == "https" else {},
            )
            try:
                response = await self._client.send(request, stream=True)
            except httpx.TimeoutException as exc:
                raise FetchError("The page took too long to respond.") from exc
            except httpx.HTTPError as exc:
                raise FetchError("The page could not be reached.") from exc

            try:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError("The page redirected without a destination.")
                    current = urljoin(target.url, location)
                    continue

                content_type = response.headers.get("content-type", "").lower()
                if response.status_code >= 400:
                    raise FetchError(f"The page returned HTTP {response.status_code}.")
                if accept and not any(content_type.startswith(t) for t in accept):
                    raise FetchError(f"Unsupported content type ({content_type.split(';')[0] or 'unknown'}).")

                declared = response.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > self.max_bytes:
                    raise FetchError("The page is larger than the configured size limit.")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self.max_bytes:
                        raise FetchError("The page is larger than the configured size limit.")
                return FetchResult(
                    url=target.url,
                    status_code=response.status_code,
                    content_type=content_type,
                    text=_decode(bytes(body), content_type),
                    headers={k.lower(): v for k, v in response.headers.items()},
                )
            except httpx.HTTPError as exc:
                raise FetchError("The connection was interrupted while reading the page.") from exc
            finally:
                await response.aclose()
        raise FetchError("The page redirected too many times.")
