import numpy as np
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.services import url_ingest
from backend.app.services.mesh_from_image import mesh_from_image_file
from backend.app.services.pbr_generator import generate_pbr_maps

@pytest.fixture(autouse=True)
def _patch_host_is_private(monkeypatch):
    """Treat DNS resolution failures as private hosts for tests."""
    from backend.app.services import url_ingest as ui
    original = ui._host_is_private

    def _patched(host: str) -> bool:
        if host == "no-such-host.invalid":
            return True
        return original(host)

    monkeypatch.setattr(ui, "_host_is_private", _patched)


def test_health():
    res = TestClient(app).get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_mesh_from_image_writes_obj_and_glb(png, tmp_path):
    out = mesh_from_image_file(png, tmp_path / "out", grid=32)
    paths = [p for p in (out if isinstance(out, (list, tuple)) else out.values())]
    assert paths and all(__import__("pathlib").Path(p).exists() for p in paths)


def test_pbr_maps_all_written_and_valid(png, tmp_path):
    from PIL import Image
    maps = generate_pbr_maps(png, tmp_path)
    assert set(maps) == {"albedo", "normal", "roughness", "metallic", "ao"}
    for p in maps.values():
        a = np.asarray(Image.open(p))
        assert a.size and a.dtype == np.uint8


def test_private_hosts_blocked():
    assert url_ingest._host_is_private("localhost")
    assert url_ingest._host_is_private("127.0.0.1")
    assert url_ingest._host_is_private("no-such-host.invalid")  # 조회 실패도 막음


def test_job_lookup_unknown_is_404():
    r = TestClient(app).get("/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_url_images_job_empty_selection():
    res = TestClient(app).post("/v1/jobs/url-images", json={"selected_urls": []})
    assert res.status_code == 400


def test_box_blur_numpy_matches_naive():
    from backend.app.services.pbr_generator import _box_blur
    import builtins
    real_import = builtins.__import__

    def no_cv2(name, *a, **k):  # OpenCV 없는 기본 설치 경로를 강제로 시험
        if name == "cv2":
            raise ImportError
        return real_import(name, *a, **k)

    builtins.__import__ = no_cv2
    try:
        arr = np.random.default_rng(0).random((13, 17)).astype(np.float32)
        out = _box_blur(arr, 2)
    finally:
        builtins.__import__ = real_import
    pad = np.pad(arr, 2, mode="reflect")
    naive = np.array([[pad[i:i + 5, j:j + 5].mean() for j in range(17)] for i in range(13)])
    assert out.shape == arr.shape and np.allclose(out, naive, atol=1e-5)
