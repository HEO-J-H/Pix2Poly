"""높이맵 메시·PBR 맵 생성이 CPU 만으로 예외 없이 도는지 (GPU·모델 다운로드 없음)."""
import numpy as np
import pytest
from PIL import Image

from backend.app.services.mesh_from_image import heightfield_mesh, mesh_from_image_file
from backend.app.services.pbr_generator import generate_pbr_maps


def _png(path, size=(32, 24)):
    rng = np.random.default_rng(0)
    Image.fromarray(rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8)).save(path)
    return path


def test_heightfield_shape_and_height():
    gray = np.linspace(0, 1, 12).reshape(3, 4)
    m = heightfield_mesh(gray, xy_scale=1.0, height_scale=0.5)
    assert len(m.vertices) >= 12 and len(m.faces) > 0
    assert m.vertices[:, 2].max() == pytest.approx(0.5, abs=1e-6)
    assert m.vertices[:, 0].min() >= -1.0 - 1e-6 and m.vertices[:, 0].max() <= 1.0 + 1e-6


def test_heightfield_too_small():
    with pytest.raises(ValueError):
        heightfield_mesh(np.zeros((1, 5)))


def test_mesh_from_image_writes_files(tmp_path):
    out = mesh_from_image_file(_png(tmp_path / "a.png"), tmp_path / "out", grid=16)
    for p in (out if isinstance(out, (tuple, list)) else out.values()):
        assert p.exists() and p.stat().st_size > 0


def test_pbr_maps_all_written(tmp_path):
    maps = generate_pbr_maps(_png(tmp_path / "b.png"), tmp_path)
    assert set(maps) == {"albedo", "normal", "roughness", "metallic", "ao"}
    for p in maps.values():
        with Image.open(p) as im:
            assert min(im.size) > 0
