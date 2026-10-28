import pytest

from app.core.errors import UnsafeURLError
from app.ingestion.url_safety import is_public_ip, normalize_url, same_site, validate_public_url
from tests.conftest import PUBLIC_IP, fake_resolver


@pytest.mark.parametrize("ip", [
    "127.0.0.1", "127.1.2.3", "10.0.0.1", "172.16.5.4", "192.168.1.1", "169.254.169.254", "0.0.0.0",
    "100.64.0.1", "224.0.0.1", "255.255.255.255", "198.18.0.1",
    "::1", "::", "fe80::1", "fd00::1", "fc00::1", "ff02::1", "::ffff:127.0.0.1", "::ffff:10.0.0.1",
    "2002:7f00:0001::1",  # 6to4 wrapping 127.0.0.1
    "64:ff9b::7f00:1",    # NAT64 wrapping 127.0.0.1
    "not-an-ip",
])
def test_non_public_addresses_are_blocked(ip: str) -> None:
    assert not is_public_ip(ip)


@pytest.mark.parametrize("ip", ["93.184.216.34", "8.8.8.8", "2606:4700:4700::1111"])
def test_public_addresses_are_allowed(ip: str) -> None:
    assert is_public_ip(ip)


@pytest.mark.parametrize("raw,expected", [
    ("example.com", "https://example.com/"),
    ("HTTPS://Example.COM/Path?utm_source=x&b=2&a=1#frag", "https://example.com/Path?a=1&b=2"),
    ("http://example.com:80/x", "http://example.com/x"),
    ("https://example.com/?fbclid=abc", "https://example.com/"),
    ("https://münchen.de/", "https://xn--mnchen-3ya.de/"),
])
def test_normalize_url(raw: str, expected: str) -> None:
    assert normalize_url(raw) == expected


@pytest.mark.parametrize("raw", [
    "file:///etc/passwd", "ftp://example.com/", "javascript:alert(1)", "gopher://x/",
    "https://user:pass@example.com/", "https://example.com:8080/", "https://example.com:22/", "", "   ",
    "data:text/html,hi",
])
def test_normalize_rejects_unsafe(raw: str) -> None:
    with pytest.raises(UnsafeURLError):
        normalize_url(raw)


@pytest.mark.parametrize("url", [
    "http://localhost/", "http://127.0.0.1/", "http://[::1]/", "http://169.254.169.254/latest/meta-data/",
    "http://metadata.google.internal/", "http://printer.local/", "http://intranet/",
    "http://evil.example/",       # resolves to loopback
    "http://mixed.example/",      # one public + one private answer
    "http://metadata.example/",   # resolves to the cloud metadata address
    "http://10.1.2.3/", "http://[fd12::1]/", "http://0x7f000001/",
])
async def test_validate_blocks_internal_targets(url: str) -> None:
    with pytest.raises(UnsafeURLError):
        await validate_public_url(url, resolver=fake_resolver)


async def test_validate_allows_public_and_pins_addresses() -> None:
    v = await validate_public_url("https://www.example.org/page", resolver=fake_resolver)
    assert v.addresses == (PUBLIC_IP,)
    assert v.host == "www.example.org" and v.port == 443


async def test_resolution_failure_is_reported_safely() -> None:
    async def failing(host: str, port: int) -> list[str]:
        raise OSError("nxdomain")

    with pytest.raises(UnsafeURLError, match="could not be resolved"):
        await validate_public_url("https://does-not-exist.example/", resolver=failing)


def test_same_site_treats_www_as_same_host() -> None:
    assert same_site("https://www.example.com/a", "example.com")
    assert not same_site("https://other.com/a", "example.com")
    assert not same_site("https://example.com.evil.com/", "example.com")
