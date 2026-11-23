"""잘못된 입력에 대한 로컬 API 에러 응답 — 사용자가 무엇이 틀렸는지 알 수 있게 4xx 와 실패 상태를 돌려주는지."""
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_single_image_without_file_is_422():
    assert client.post("/v1/jobs/single-image").status_code == 422


def test_multi_image_needs_two():
    r = client.post("/v1/jobs/multi-image", files=[("files", ("a.png", b"x", "image/png"))])
    assert r.status_code == 400 and "At least" in r.json()["detail"]


def test_broken_image_job_ends_failed():
    r = client.post("/v1/jobs/single-image", files={"file": ("bad.png", b"not an image", "image/png")})
    assert r.status_code == 200
    job = client.get(f"/v1/jobs/{r.json()['job_id']}").json()
    assert job["status"] == "failed" and job["message"]


def test_url_job_rejects_non_http_scheme():
    assert client.post("/v1/jobs/url", json={"page_url": "ftp://example.com/x"}).status_code == 422


def test_malformed_job_id_is_422():  # 형식이 틀린 작업 번호는 찾아보기 전에 거절 (없는 번호는 404 — test_core)
    assert client.get("/v1/jobs/does-not-exist").status_code == 422
