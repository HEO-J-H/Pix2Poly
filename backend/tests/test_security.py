import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import url_ingest as ui


@pytest.mark.parametrize("url", ["http://127.0.0.1:8000/", "http://169.254.169.254/latest/meta-data",
                                 "http://10.0.0.1/a.png", "http://0.0.0.0/", "file:///etc/passwd", "http://localhost/"])
def test_blocks_internal_urls(url):
    with pytest.raises(ui.BlockedURL):
        ui.check_public_url(url)


def test_redirect_to_internal_is_blocked(monkeypatch):
    import httpx

    def handler(req):
        if req.url.host == "example.com":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
        return httpx.Response(200, content=b"secret")
    monkeypatch.setattr(ui, "_host_is_private", lambda h: h in ("127.0.0.1", "localhost"))

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False) as c:
            await ui.safe_get(c, "http://example.com/a.png", 1024)
    with pytest.raises(ui.BlockedURL):
        asyncio.run(go())


def test_size_limit(monkeypatch):
    import httpx
    monkeypatch.setattr(ui, "_host_is_private", lambda h: False)

    async def go():
        t = httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 5000))
        async with httpx.AsyncClient(transport=t) as c:
            await ui.safe_get(c, "http://example.com/big", 1000)
    with pytest.raises(ValueError):
        asyncio.run(go())


def test_cors_rejects_random_site():
    r = TestClient(app).options("/health", headers={"Origin": "https://evil.example",
                                                     "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") != "https://evil.example"


def test_sibling_folder_path_rejected():
    from backend.app.services import storage
    with pytest.raises(ValueError):
        storage.resolve_under_uploads("uploads_evil/x.png")
