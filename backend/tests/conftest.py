"""테스트는 실제 uploads/outputs 를 건드리지 않도록 임시 폴더 사용, GPU·외부 도구(COLMAP·Blender·TripoSR) 없이 동작."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def png(tmp_path):
    from PIL import Image
    p = tmp_path / "in.png"
    img = Image.new("RGB", (64, 64), (120, 90, 60))
    for x in range(64):
        img.putpixel((x, x), (250, 250, 250))  # 높이 변화가 생기도록 대각선
    img.save(p)
    return p
