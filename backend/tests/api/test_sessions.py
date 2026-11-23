from dataclasses import replace

import httpx
import pytest

from lumiere.main import create_app
from tests.api.conftest import Api


@pytest.mark.parametrize("scheme", ["http", "https"])
async def test_session_cookie_and_reuse(api: Api, scheme: str) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(api.services)), base_url=f"{scheme}://app.test") as client:
        response = await client.post("/api/v1/guest-session")
        assert response.status_code == 200 and response.content == b""
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-lumiere-guest-created"] == "true"
        assert (await client.post("/api/v1/guest-session")).headers["x-lumiere-guest-created"] == "false"
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
        assert ("secure" in cookie) == (scheme == "https")
        assert "max-age=31536000" in cookie
        assert "max-age=31536000" in (await client.post("/api/v1/guest-session")).headers["set-cookie"].lower()


async def test_bootstrap_origin_protection(api: Api) -> None:
    for headers in ({"origin": "https://evil.test"}, {"sec-fetch-site": "cross-site"}):
        response = await api.client.post("/api/v1/guest-session", headers=headers)
        assert response.status_code == 500
        assert response.headers["cache-control"] == "no-store"
        assert "set-cookie" not in response.headers


async def test_forged_forwarding_headers_are_ignored(api: Api) -> None:
    from starlette.requests import Request

    from lumiere.adapters.inbound.http.context import quota_ip_key

    def request(peer: str, forwarded: str) -> Request:
        return Request({"type": "http", "client": (peer, 1234), "headers": [(b"x-forwarded-for", forwarded.encode())], "scheme": "http", "server": ("app.test", 80), "path": "/"})

    a = quota_ip_key(request("127.0.0.1", "1.2.3.4"), api.services)
    assert a == quota_ip_key(request("127.0.0.1", "8.8.8.8"), api.services)
    services = replace(api.services, trusted_proxy_cidrs=("127.0.0.0/8",))
    assert quota_ip_key(request("127.0.0.1", "2001:db8::1"), services) == quota_ip_key(request("127.0.0.1", "2001:0db8:0:0:0:0:0:1"), services)
    assert quota_ip_key(request("127.0.0.1", "1.2.3.4, 127.0.0.2"), services) == quota_ip_key(request("127.0.0.1", "1.2.3.4"), services)
