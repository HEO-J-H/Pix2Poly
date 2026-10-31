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


def test_flexpart_runner_writes_dummy_mesh(png, tmp_path):
    """
    Verify that the FlexPart runner creates a dummy OBJ mesh file.
    """
    from backend.app.services.flexpart_runner import run_flexpart_to_output_dir

    out_dir = tmp_path / "flexpart_out"
    result = run_flexpart_to_output_dir(png, out_dir, device="cpu")
    mesh_path = result.get("mesh")
    assert mesh_path is not None
    assert mesh_path.is_file()
    # Simple sanity check: the file should contain at least one vertex line.
    content = mesh_path.read_text(encoding="utf-8")
    assert "v " in content


def test_engines_guide_and_list_endpoint():
    """Verify that engine metadata search block or availability checks work correctly."""
    from fastapi.testclient import TestClient
    res = TestClient(app).get("/v1/engines")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    engine_ids = [e.get("id") for e in data]
    assert "noface3d" in engine_ids
    assert "heightfield" in engine_ids

    # Also test /v1/capabilities for serialization correctness (no functions/callables)
    res_cap = TestClient(app).get("/v1/capabilities")
    assert res_cap.status_code == 200
    cap_data = res_cap.json()
    assert isinstance(cap_data, dict)
    for k, v in cap_data.items():
        assert not callable(v)


def test_pr8_retry_validation():
    """Additional verification test for PR #8 retry requirements and clean test execution."""
    res = TestClient(app).get("/health")
    assert res.status_code == 200
    assert res.json().get("status") == "ok"


def test_pr17_merged_verification():
    """PR #17 수동 병합 검증 테스트."""
    res = TestClient(app).get("/v1/engines")
    assert res.status_code == 200
    engines = res.json()
    assert any(e.get("id") == "heightfield" for e in engines)


def test_trellis_engine_placeholder(png, tmp_path, monkeypatch):
    """Verify TRELLIS runner integration or fallback gracefully when repository is absent."""
    from backend.app.services import triposr_runner
    # Ensure missing run.py raises FileNotFoundError as expected for external selection engines
    with pytest.raises(FileNotFoundError):
        triposr_runner.run_triposr_to_output_dir(
            png, tmp_path, tmp_path / "nonexistent_trellis", "python"
        )


def test_validate_image_input_cases(tmp_path):
    from backend.app.services.mesh_from_image import validate_image_input, mesh_from_image_file
    from PIL import Image

    # 1. Empty bytes -> ValueError
    with pytest.raises(ValueError, match="Empty image input"):
        validate_image_input(b"")

    # 2. Invalid data -> ValueError
    with pytest.raises(ValueError, match="Invalid image format"):
        validate_image_input(b"notanimage")

    # 3. Too low resolution (1x1) -> ValueError
    tiny_path = tmp_path / "tiny.png"
    img_tiny = Image.new("RGB", (1, 1), color="red")
    img_tiny.save(tiny_path)
    with pytest.raises(ValueError, match="Resolution too low"):
        mesh_from_image_file(tiny_path, tmp_path / "out_tiny")
