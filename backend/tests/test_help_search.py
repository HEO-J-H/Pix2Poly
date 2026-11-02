from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import help_search


def test_search_finds_relevant_section():
    hits = help_search.search("사진 몇 장 찍어야 해?")
    assert hits and any("장" in h["text"] for h in hits)
    assert help_search.search("zzqx qqvv") == []


def test_help_endpoint():
    r = TestClient(app).get("/v1/help/search", params={"q": "GLB 와 OBJ 차이"})
    assert r.status_code == 200 and r.json()["results"]
    assert "GLB" in r.json()["results"][0]["text"] or "GLB" in r.json()["results"][0]["title"]
