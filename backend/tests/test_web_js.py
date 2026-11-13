"""웹(브라우저) 높이맵·PBR 계산 테스트를 백엔드 테스트와 함께 실행 — node 가 있을 때만 (없으면 건너뜀)."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_web_heightfield_and_pbr_js():
    r = subprocess.run(["node", "--test", str(ROOT / "web" / "tests" / "pix2poly.test.mjs")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-1000:]
