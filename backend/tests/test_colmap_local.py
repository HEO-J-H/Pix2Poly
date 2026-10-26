from pathlib import Path

import pytest

from backend.app.services import colmap_runner as cr


def test_vertex_count(tmp_path):
    p = tmp_path / "a.ply"
    p.write_bytes(b"ply\nformat ascii 1.0\nelement vertex 42\nend_header\n")
    assert cr._ply_vertex_count(p) == 42


def test_too_few_points_explains(tmp_path, monkeypatch):
    p = tmp_path / "s.ply"
    p.write_bytes(b"ply\nelement vertex 160\nend_header\n")
    monkeypatch.setattr(cr, "run_colmap_sfm", lambda *a, **k: p)
    with pytest.raises(RuntimeError, match="160"):
        cr.run_colmap_pipeline(tmp_path, tmp_path / "out")


def test_gpu_follows_build(monkeypatch):
    monkeypatch.delenv("PIX2POLY_COLMAP_GPU", raising=False)
    monkeypatch.setattr(cr, "colmap_has_cuda", lambda: True)
    assert cr._use_gpu() == 1
    monkeypatch.setenv("PIX2POLY_COLMAP_GPU", "0")
    assert cr._use_gpu() == 0


def test_black_share_ignores_empty_atlas(tmp_path):
    import numpy as np
    from PIL import Image
    a = np.zeros((10, 10, 3), dtype=np.uint8)
    a[:, :5] = (255, 127, 39)   # OpenMVS 빈칸(주황) — 계산에서 제외
    a[:, 5:8] = (120, 200, 90)  # 색 있음
    Image.fromarray(a).save(tmp_path / "t.png")  # 나머지 2열은 검정
    assert abs(cr._black_share(tmp_path / "t.png") - 0.4) < 1e-6


def test_texture_skipped_without_openmvs(tmp_path, monkeypatch):
    monkeypatch.setattr(cr, "MVS_DIR", tmp_path / "none")
    assert cr.texture_mesh(tmp_path, tmp_path / "m.ply", tmp_path / "out") is None
