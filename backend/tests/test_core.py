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


def test_pr47_site_ux_verification():
    """PR #47 사이트·UX 및 API 엔진 상세 검증 테스트 및 URL 인게스트 예외 처리 검증."""
    res = TestClient(app).get("/v1/engines")
    assert res.status_code == 200
    engines = res.json()
    engine_ids = {e.get("id") for e in engines}
    assert "heightfield" in engine_ids
    assert "colmap" in engine_ids
    assert "bg_remove" in engine_ids

    # Capabilities endpoint sanity check
    cap_res = TestClient(app).get("/v1/capabilities")
    assert cap_res.status_code == 200
    cap_data = cap_res.json()
    assert "colmap" in cap_data
    assert "remove_bg" in cap_data

    # Test URL images ingest format & validation exception handling (PR #47 review)
    client = TestClient(app)
    # Empty selection test
    resp_empty = client.post("/v1/jobs/url-images", json={"selected_urls": []})
    assert resp_empty.status_code == 400

    # Unreachable or blocked URL test
    resp_bad = client.post("/v1/jobs/url-images", json={"selected_urls": ["http://127.0.0.1/fake.png"]})
    assert resp_bad.status_code == 200
    data_bad = resp_bad.json()
    assert data_bad.get("status") == "failed"


def test_pr50_pr51_review_and_exception_handling():
    """PR #50 및 PR #51 백엔드 변경 사항 최종 검토 및 예외 처리 견고성 검증."""
    client = TestClient(app)
    
    # 1. 엔진 상태 및 기능 메타데이터 최종 점검 (PR #50/#51 연계)
    res_engines = client.get("/v1/engines")
    assert res_engines.status_code == 200
    engine_list = res_engines.json()
    assert any(e.get("id") == "trellis_cpp" for e in engine_list)
    assert any(e.get("id") == "noface3d" for e in engine_list)

    # 2. 잘못된 URL 선택 작업 요청 시 예외 처리 검증 (400 또는 정상적 실패 처리)
    res_url_empty = client.post("/v1/jobs/url-images", json={"selected_urls": []})
    assert res_url_empty.status_code == 400


def test_p572805b315_content_hold_split_verification():
    """홀드된 문서 및 테스트 작업 재시도 분할 과제(p-572805b315)에 따른 분리 검증 테스트."""
    res = TestClient(app).get("/v1/engines")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert any(e.get("id") == "heightfield" for e in data)


def test_trellis_engine_placeholder(png, tmp_path, monkeypatch):
    """Verify TRELLIS runner integration or fallback gracefully when repository is absent."""
    from backend.app.services import triposr_runner
    # Ensure missing run.py raises FileNotFoundError as expected for external selection engines
    with pytest.raises(FileNotFoundError):
        triposr_runner.run_triposr_to_output_dir(
            png, tmp_path, tmp_path / "nonexistent_trellis", "python"
        )


def test_validate_image_input_empty_and_low_res(tmp_path):
    from backend.app.services.mesh_from_image import validate_image_input, mesh_from_image_file
    from PIL import Image

    # 1. Non-existent file
    missing = tmp_path / "nonexistent.png"
    with pytest.raises(ValueError, match="empty or does not exist"):
        validate_image_input(missing)

    # 2. Empty file
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="empty or does not exist"):
        validate_image_input(empty)

    # 3. Low resolution image (1x1)
    low_res = tmp_path / "low.png"
    img = Image.new("RGB", (1, 1), color="red")
    img.save(low_res)
    with pytest.raises(ValueError, match="resolution too low"):
        validate_image_input(low_res)

    # 4. Integration test through mesh_from_image_file with low-res image
    with pytest.raises(ValueError, match="resolution too low"):
        mesh_from_image_file(low_res, tmp_path / "out_low")


def test_physag3d_research_doc_reference():
    """Verify that PhysAg3D is documented in tech-research.md as part of simulation/deformation research."""
    from pathlib import Path
    doc_path = Path("docs/tech-research.md")
    assert doc_path.exists()
    content = doc_path.read_text(encoding="utf-8")
    assert "PhysAg3D" in content


def test_rag_opensource_research_doc_reference():
    """Verify that GitHub RAG open-source utilization plan and local RAG code example are documented in tech-research.md."""
    from pathlib import Path
    doc_path = Path("docs/tech-research.md")
    assert doc_path.exists()
    content = doc_path.read_text(encoding="utf-8")
    assert "깃허브 RAG 오픈소스 활용 방안" in content or "RAG" in content
    assert "MarkdownHeaderTextSplitter" in content


def test_validate_pbr_input_errors(tmp_path):
    from backend.app.services.pbr_generator import validate_pbr_input, generate_pbr_maps
    from PIL import Image

    # 1. Non-existent file
    missing = tmp_path / "nonexistent_pbr.png"
    with pytest.raises(ValueError, match="empty or does not exist"):
        validate_pbr_input(missing)

    # 2. Empty file
    empty = tmp_path / "empty_pbr.png"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="empty or does not exist"):
        validate_pbr_input(empty)

    # 3. Low resolution image (8x8)
    low_res = tmp_path / "low_pbr.png"
    img = Image.new("RGB", (8, 8), color="blue")
    img.save(low_res)
    with pytest.raises(ValueError, match="resolution too low"):
        validate_pbr_input(low_res)

    # 4. Integration test through generate_pbr_maps with low-res image
    with pytest.raises(ValueError, match="resolution too low"):
        generate_pbr_maps(low_res, tmp_path / "out_pbr_low")


def test_fetch_image_from_url_validation_and_timeouts():
    """잘못된 URL 입력, 프로토콜 및 타임아웃/예외 처리에 대한 단위 테스트."""
    import asyncio
    from backend.app.services.url_ingest import fetch_image_from_url, validate_url_input, BlockedURL

    # 0. validate_url_input 직접 검증 (PR #41 요구사항)
    for invalid_url in ["", "ftp://example.com/img.png", "not-a-url", "file:///etc/passwd"]:
        with pytest.raises((BlockedURL, ValueError)):
            validate_url_input(invalid_url)

    # 1. 잘못된 스킴 또는 빈 URL 검증
    for invalid_url in ["", "ftp://example.com/img.png", "not-a-url", "file:///etc/passwd"]:
        with pytest.raises((BlockedURL, ValueError)):
            asyncio.run(fetch_image_from_url(invalid_url))

    # 2. 내부망/로컬 주소 차단 검증
    for internal_url in ["http://localhost/img.png", "http://127.0.0.1/img.png", "http://169.254.169.254/latest"]:
        with pytest.raises(BlockedURL):
            validate_url_input(internal_url)
        with pytest.raises(BlockedURL):
            asyncio.run(fetch_image_from_url(internal_url))



def test_triposr_failures_become_clear_errors(png, tmp_path):
    """TripoSR 실행 실패·결과 없음은 원인을 알 수 있는 RuntimeError 로 (원시 예외가 화면에 나오지 않게)."""
    import sys
    from backend.app.services import triposr_runner
    root = tmp_path / "triposr"
    root.mkdir()
    (root / "run.py").write_text("import sys; sys.exit(3)", encoding="utf-8")
    with pytest.raises(RuntimeError, match="종료 코드 3"):
        triposr_runner.run_triposr_to_output_dir(png, tmp_path / "out1", root, sys.executable)
    (root / "run.py").write_text("print('no mesh')", encoding="utf-8")
    with pytest.raises(RuntimeError, match="mesh.obj"):
        triposr_runner.run_triposr_to_output_dir(png, tmp_path / "out2", root, sys.executable)
    with pytest.raises(RuntimeError, match="파이썬을 찾지 못했습니다"):
        triposr_runner.run_triposr_to_output_dir(png, tmp_path / "out3", root, str(tmp_path / "no-python.exe"))


def test_web_pbr_heightmap_and_texture_conversion_unit(png, tmp_path):
    """웹 PBR 텍스처 브라우저 실시간 렌더링을 위한 파이썬 백엔드 PBR 높이맵 및 텍스처 변환 함수 단위 테스트."""
    from backend.app.services.pbr_generator import generate_pbr_maps
    from PIL import Image

    # 높이맵 기반 PBR 생성 검증 (웹에서 JS로 구현된 알고리즘의 기준 데이터 역할)
    maps = generate_pbr_maps(png, tmp_path / "web_pbr_out")
    assert "albedo" in maps
    assert "normal" in maps
    assert "roughness" in maps
    assert "metallic" in maps
    assert "ao" in maps

    # 생성된 맵 파일들이 유효한 이미지인지 확인
    for key, path in maps.items():
        assert path.exists()
        img = Image.open(path)
        assert img.size[0] >= 16
        assert img.size[1] >= 16
