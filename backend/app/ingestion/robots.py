"""robots.txt handling. Fetched through the same SSRF-safe fetcher."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from app.ingestion.fetcher import FetchError, SafeFetcher


class RobotsPolicy:
    def __init__(self, parser: RobotFileParser | None, user_agent: str, *, allow_all: bool = False,
                 disallow_all: bool = False) -> None:
        self._parser = parser
        self._ua = user_agent
        self._allow_all = allow_all
        self._disallow_all = disallow_all

    def allowed(self, url: str) -> bool:
        if self._disallow_all:
            return False
        if self._allow_all or self._parser is None:
            return True
        return self._parser.can_fetch(self._ua, url)

    def crawl_delay(self) -> float | None:
        if self._parser is None:
            return None
        delay = self._parser.crawl_delay(self._ua)
        return float(delay) if delay is not None else None

    @property
    def disallow_all(self) -> bool:
        return self._disallow_all


async def load_robots(fetcher: SafeFetcher, site_url: str) -> RobotsPolicy:
    parts = urlsplit(site_url)
    robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
    ua_token = fetcher.user_agent.split("/")[0]
    try:
        result = await fetcher.fetch(robots_url, accept=())
    except FetchError as exc:
        message = str(exc)
        if "HTTP 401" in message or "HTTP 403" in message:
            return RobotsPolicy(None, ua_token, disallow_all=True)
        if "HTTP 4" in message:  # 404 etc.: no robots.txt means no restrictions
            return RobotsPolicy(None, ua_token, allow_all=True)
        # Server errors / unreachable robots.txt: be conservative and do not crawl.
        return RobotsPolicy(None, ua_token, disallow_all=True)
    parser = RobotFileParser()
    parser.parse(result.text.splitlines())
    return RobotsPolicy(parser, ua_token)
