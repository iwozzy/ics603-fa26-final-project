from http.cookies import SimpleCookie

import httpx
import pytest

from lumiere.main import create_app
from tests.api.conftest import Api


@pytest.mark.parametrize("scheme", ["http", "https"])
async def test_bootstrap_sets_persistent_cookie_and_renews_same_identity(api: Api, scheme: str) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(api.services)), base_url=f"{scheme}://app.test") as client:
        values: list[str] = []
        for _ in range(2):
            response = await client.post("/api/v1/guest-session")
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            cookies = SimpleCookie()
            cookies.load(response.headers["set-cookie"])
            assert len(cookies) == 1
            cookie = next(iter(cookies.values()))
            assert cookie["max-age"] == "31536000"
            assert cookie["httponly"]
            assert cookie["samesite"].lower() == "lax"
            assert cookie["path"] == "/"
            assert bool(cookie["secure"]) == (scheme == "https")
            values.append(cookie.value)
        assert values[0] == values[1]
