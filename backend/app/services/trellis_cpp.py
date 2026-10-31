"""trellis.cpp (TRELLIS.2 의 C++ 포트) — 로컬 GPU 로 사진 1장 → 입체 GLB. 선택 엔진 (설치한 사람만).

설정 (환경변수, 저장소에 실행 파일·모델을 넣지 않음 — docs/agent-guides/trellis_integration.md):
  TRELLIS_CPP_BIN    실행 파일 경로 (github.com/pwilkin/trellis.cpp 릴리스)
  TRELLIS_CPP_MODEL  GGUF 모델 파일 경로
  TRELLIS_CPP_ARGS   인자 형식 (기본: "-m {model} -i {image} -o {out}") — 버전에 따라 다르면 README 를 보고 바꿈

안전: 셸을 거치지 않고(shell=False) 인자 목록으로만 실행, 실행 파일·모델·입력 파일이 실제로 있는지 먼저 확인,
시간 제한, 결과 파일이 생겼는지 확인. 실패는 한국어 RuntimeError.
"""
from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

DEFAULT_ARGS = "-m {model} -i {image} -o {out}"
DEFAULT_TIMEOUT = 900


def _paths() -> tuple[Path | None, Path | None]:
    b, m = os.environ.get("TRELLIS_CPP_BIN", "").strip(), os.environ.get("TRELLIS_CPP_MODEL", "").strip()
    return (Path(b) if b else None), (Path(m) if m else None)


def available() -> tuple[bool, str]:
    """(쓸 수 있나, 이유) — 화면에 '설치 안 됨' 안내를 그대로 보여 줄 수 있게."""
    exe, model = _paths()
    if not exe:
        return False, "trellis.cpp 미설치 — TRELLIS_CPP_BIN 에 실행 파일 경로를 설정하세요"
    if not exe.is_file():
        return False, f"실행 파일을 찾을 수 없음: {exe}"
    if not model or not model.is_file():
        return False, "GGUF 모델 파일이 없음 — TRELLIS_CPP_MODEL 을 설정하세요"
    return True, "사용 가능"


def build_command(image: Path, out_glb: Path) -> list[str]:
    exe, model = _paths()
    template = os.environ.get("TRELLIS_CPP_ARGS", "").strip() or DEFAULT_ARGS
    parts = shlex.split(template, posix=os.name != "nt")
    args = [p.format(model=str(model), image=str(image), out=str(out_glb)) for p in parts]
    return [str(exe), *args]


def run(image_path: Path, out_glb: Path, timeout: int = DEFAULT_TIMEOUT) -> Path:
    ok, why = available()
    if not ok:
        raise RuntimeError(why)
    image_path, out_glb = Path(image_path), Path(out_glb)
    if not image_path.is_file():
        raise RuntimeError(f"입력 이미지가 없습니다: {image_path.name}")
    out_glb.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_command(image_path, out_glb)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False, errors="replace")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"trellis.cpp 가 {timeout}초 안에 끝나지 않았습니다 (GPU 메모리·모델 크기 확인)") from None
    except OSError as e:
        raise RuntimeError(f"trellis.cpp 를 실행하지 못했습니다: {e}") from None
    if r.returncode != 0:
        raise RuntimeError(f"trellis.cpp 실패 (종료 코드 {r.returncode}): {(r.stderr or r.stdout)[-400:]}")
    if not out_glb.is_file() or out_glb.stat().st_size == 0:
        raise RuntimeError("trellis.cpp 가 끝났지만 GLB 파일이 만들어지지 않았습니다 (인자 형식 TRELLIS_CPP_ARGS 확인)")
    return out_glb
