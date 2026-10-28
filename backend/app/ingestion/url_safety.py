"""URL normalization and SSRF protection.

Rules enforced before any outbound request (and again for every redirect hop):
  * only http/https, only ports 80/443, no embedded credentials;
  * hostnames such as localhost / *.internal / *.local are rejected outright;
  * every address the hostname resolves to must be a public, globally routable
    unicast address (IPv4 and IPv6, including IPv4-mapped / 6to4 / Teredo forms);
  * the fetcher then connects to the *validated* IP (DNS pinning) so a second,
    attacker-controlled DNS answer cannot redirect the connection (rebinding).
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.errors import UnsafeURLError

ALLOWED_SCHEMES = {"http", "https"}
DEFAULT_PORTS = {"http": 80, "https": 443}
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "metadata",
    "metadata.google.internal",
    "instance-data",
    "instance-data.ec2.internal",
}
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".intranet", ".lan", ".home.arpa", ".corp")
TRACKING_PARAMS_PREFIXES = ("utm_",)
TRACKING_PARAMS = {"fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "ref_src", "igshid"}

# Explicit deny-list on top of ipaddress.is_global, for clarity and defence in depth.
_BLOCKED_NETWORKS = [ipaddress.ip_network(n) for n in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16",
    "172.16.0.0/12", "192.0.0.0/24", "192.0.2.0/24", "192.88.99.0/24", "192.168.0.0/16",
    "198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24", "224.0.0.0/4", "240.0.0.0/4",
    "255.255.255.255/32",
    "::/128", "::1/128", "::ffff:0:0/96", "64:ff9b::/96", "64:ff9b:1::/48", "100::/64",
    "2001::/23", "2001:db8::/32", "fc00::/7", "fe80::/10", "fec0::/10", "ff00::/8",
)]

Resolver = Callable[[str, int], Awaitable[list[str]]]


@dataclass(frozen=True)
class ValidatedURL:
    url: str
    scheme: str
    host: str  # ASCII (IDNA) hostname, or bare IP
    port: int
    addresses: tuple[str, ...]


def is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        # Embedded IPv4 forms must be checked as IPv4.
        if ip.ipv4_mapped is not None:
            return is_public_ip(str(ip.ipv4_mapped))
        if ip.sixtofour is not None:
            return is_public_ip(str(ip.sixtofour))
        if ip.teredo is not None:
            return all(is_public_ip(str(part)) for part in ip.teredo)
    if any(ip in net for net in _BLOCKED_NETWORKS if net.version == ip.version):
        return False
    return ip.is_global and not (ip.is_multicast or ip.is_reserved or ip.is_loopback
                                 or ip.is_link_local or ip.is_private or ip.is_unspecified)


def _idna(host: str) -> str:
    try:
        return host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise UnsafeURLError("The URL hostname is not valid.") from exc


def normalize_url(raw: str, *, base: str | None = None) -> str:
    """Normalize a user- or page-supplied URL. Raises UnsafeURLError if malformed/unsupported."""
    from urllib.parse import urljoin

    if not isinstance(raw, str) or not raw.strip():
        raise UnsafeURLError("Please provide a URL.")
    raw = raw.strip()
    if len(raw) > 2048:
        raise UnsafeURLError("The URL is too long.")
    if base:
        raw = urljoin(base, raw)
    elif "://" not in raw:
        raw = "https://" + raw

    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError("Only http and https URLs are supported.")
    if parts.username or parts.password:
        raise UnsafeURLError("URLs containing credentials are not allowed.")
    if not parts.hostname:
        raise UnsafeURLError("The URL must include a hostname.")
    try:
        port = parts.port
    except ValueError as exc:
        raise UnsafeURLError("The URL port is not valid.") from exc

    host = parts.hostname.rstrip(".")
    try:
        ip = ipaddress.ip_address(host)
        host_out = f"[{ip}]" if ip.version == 6 else str(ip)
    except ValueError:
        host = _idna(host)
        host_out = host
    if port is not None and port != DEFAULT_PORTS[scheme]:
        if port not in (80, 443):
            raise UnsafeURLError("Only standard web ports (80 and 443) are allowed.")
        host_out = f"{host_out}:{port}"

    query_pairs = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith(TRACKING_PARAMS_PREFIXES)
    ]
    query = urlencode(sorted(query_pairs), doseq=True)
    path = parts.path or "/"
    return urlunsplit((scheme, host_out, path, query, ""))


async def system_resolver(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


async def validate_public_url(url: str, *, resolver: Resolver = system_resolver,
                              allow_private: bool = False) -> ValidatedURL:
    """Normalize, then resolve and verify that every resolved address is public."""
    normalized = normalize_url(url)
    parts = urlsplit(normalized)
    scheme = parts.scheme
    host = (parts.hostname or "").lower()
    port = parts.port or DEFAULT_PORTS[scheme]

    if not allow_private:
        if host in BLOCKED_HOSTNAMES or host.endswith(BLOCKED_SUFFIXES) or "." not in host and ":" not in host:
            raise UnsafeURLError("This address points to a local or internal network and cannot be crawled.")

    try:
        literal = ipaddress.ip_address(host)
        addresses = [str(literal)]
    except ValueError:
        try:
            addresses = await resolver(host, port)
        except (OSError, UnicodeError) as exc:
            raise UnsafeURLError("The website's hostname could not be resolved.") from exc
    if not addresses:
        raise UnsafeURLError("The website's hostname could not be resolved.")
    if not allow_private and not all(is_public_ip(a) for a in addresses):
        raise UnsafeURLError("This address points to a private, local or reserved network and cannot be crawled.")
    return ValidatedURL(url=normalized, scheme=scheme, host=host, port=port, addresses=tuple(addresses))


def same_site(url: str, root_host: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    strip = lambda h: h[4:] if h.startswith("www.") else h  # noqa: E731
    return strip(host) == strip(root_host.lower())
