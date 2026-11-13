"""원본 Microsoft TRELLIS (Python, MIT) — 로컬 GPU 로 사진 1장 또는 여러 각도 사진 → 입체 GLB. 선택 엔진 (설치한 사람만).

trellis_cpp.py(C++ 포트, 단독 실행 파일)와 같은 방식: 저장소에 코드·가중치를 넣지 않고, 사용자가 설치한 환경을 경로로만 받는다.
설정 (환경변수):
  TRELLIS_REPO    github.com/microsoft/TRELLIS 를 받아 setup 한 폴더
  TRELLIS_PYTHON  그 환경의 python 실행 파일 (conda/venv) — 기본 python
  TRELLIS_MODEL   기본 microsoft/TRELLIS-image-large
요구: NVIDIA GPU(VRAM 16GB 이상 권장, README 기준)·CUDA — Windows 가정용 PC 는 trellis_cpp 쪽이 맞을 수 있음.
안전: 셸 없이(shell=False) 인자 목록으로, 입력·폴더 존재 확인, 시간 제한, 결과 파일 확인. 실패는 한국어 RuntimeError.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

DEFAULT_MODEL = "microsoft/TRELLIS-image-large"
DEFAULT_TIMEOUT = 1800

# TRELLIS 저장소 README 의 사용 예 그대로 (이미지 1장: run, 여러 장: run_multi_image → GLB)
DRIVER = r'''
import json, os, sys
os.environ.setdefault("SPCONV_ALGO", "native")
from PIL import Image
from trellis.pipelines import TrellisImageTo3DPipeline
from trellis.utils import postprocessing_utils
args = json.loads(sys.argv[1])
pipe = TrellisImageTo3DPipeline.from_pretrained(args["model"])
pipe.cuda()
imgs = [Image.open(p) for p in args["images"]]
if len(imgs) == 1:
    out = pipe.run(imgs[0], seed=args["seed"])
else:
    out = pipe.run_multi_image(imgs, seed=args["seed"])
glb = postprocessing_utils.to_glb(out["gaussian"][0], out["mesh"][0], simplify=0.95, texture_size=1024)
glb.export(args["out"])
'''


def _cfg() -> tuple[Path | None, str, str]:
    repo = os.environ.get("TRELLIS_REPO", "").strip()
    return (Path(repo) if repo else None), (os.environ.get("TRELLIS_PYTHON", "").strip() or "python"), \
        (os.environ.get("TRELLIS_MODEL", "").strip() or DEFAULT_MODEL)


def available() -> tuple[bool, str]:
    """(쓸 수 있나, 이유) — 화면에 '설치 안 됨' 안내를 그대로 보여 줄 수 있게."""
    repo, _py, _model = _cfg()
    if not repo:
        return False, "TRELLIS 미설치 — TRELLIS_REPO 에 github.com/microsoft/TRELLIS 설치 폴더를 지정하세요"
    if not (repo / "trellis").is_dir():
        return False, f"TRELLIS 폴더에 trellis 패키지가 없습니다: {repo}"
    return True, "사용 가능 (원본 TRELLIS, 로컬 GPU)"


def run(images: list[str | Path], out_glb: str | Path, timeout: int = DEFAULT_TIMEOUT, seed: int = 1) -> Path:
    """사진 1장 또는 여러 각도 사진 → GLB. 성공하면 out_glb 경로."""
    ok, why = available()
    if not ok:
        raise RuntimeError(why)
    repo, py, model = _cfg()
    imgs = [Path(p) for p in images]
    if not imgs:
        raise RuntimeError("TRELLIS 에 넣을 사진이 없습니다")
    missing = [str(p) for p in imgs if not p.is_file()]
    if missing:
        raise RuntimeError(f"사진 파일을 찾지 못했습니다: {', '.join(missing[:3])}")
    out = Path(out_glb)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="trellis_") as tmp:
        driver = Path(tmp) / "run_trellis.py"
        driver.write_text(DRIVER, encoding="utf-8")
        args = json.dumps({"model": model, "images": [str(p.resolve()) for p in imgs], "out": str(out.resolve()), "seed": seed})
        try:
            subprocess.run([py, str(driver), args], cwd=str(repo), check=True, timeout=timeout, shell=False,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"TRELLIS 가 {timeout}초 안에 끝나지 않았습니다 — GPU·VRAM(16GB 이상 권장)을 확인하세요") from e
        except subprocess.CalledProcessError as e:
            tail = (e.stderr or "").strip().splitlines()[-1:] or [""]
            raise RuntimeError(f"TRELLIS 실행 실패 (종료 코드 {e.returncode}) {tail[0][:200]}") from e
        except OSError as e:
            raise RuntimeError(f"TRELLIS 를 실행할 파이썬을 찾지 못했습니다 ({py}): {e}") from e
    if not out.is_file() or out.stat().st_size == 0:
        raise RuntimeError("TRELLIS 가 GLB 를 만들지 못했습니다 — 콘솔의 CUDA 오류를 확인하세요")
    return out
