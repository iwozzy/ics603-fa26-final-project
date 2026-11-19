import hashlib
import hmac
from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network
from urllib.parse import urlsplit

from fastapi import Request

from lumiere.adapters.inbound.http.deps import HttpServices
from lumiere.domain.errors import SearchFailed

COOKIE_NAME = "lumiere_guest"


def _address(raw: str) -> IPv4Address | IPv6Address:
    address = ip_address(raw)
    return address.ipv4_mapped or address if isinstance(address, IPv6Address) else address


def _trusted(raw: str, services: HttpServices) -> bool:
    address = _address(raw)
    return any(address in ip_network(cidr) for cidr in services.trusted_proxy_cidrs)


def quota_ip_key(request: Request, services: HttpServices) -> str:
    try:
        peer = request.client.host if request.client else ""
        current = peer
        if _trusted(peer, services):
            for raw in reversed(request.headers.get("x-forwarded-for", "").split(",")):
                if raw.strip() and _trusted(current, services):
                    current = str(_address(raw.strip()))
        normalized = str(_address(current))
    except ValueError:
        raise SearchFailed("client_context") from None
    return hmac.new(services.ip_hash_key, normalized.encode(), hashlib.sha256).hexdigest()


def transport_scheme(request: Request, services: HttpServices) -> str:
    if request.client and _trusted(request.client.host, services):
        forwarded = request.headers.get("x-forwarded-proto")
        if forwarded in ("http", "https"):
            return forwarded
    return request.url.scheme


def check_origin(request: Request, services: HttpServices) -> None:
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise SearchFailed("origin")
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme != transport_scheme(request, services) or parsed.netloc != request.url.netloc:
            raise SearchFailed("origin")
