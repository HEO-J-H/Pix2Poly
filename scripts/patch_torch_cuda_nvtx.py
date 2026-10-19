"""Patch PyTorch cuda.cmake so find_package(Torch) finds nvtx3 from CUDA toolkit (Windows torchmcubes)."""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: patch_torch_cuda_nvtx.py <TripoSR_root>", file=sys.stderr)
        return 2
    tr = Path(sys.argv[1]).resolve()
    cm = tr / ".venv" / "Lib" / "site-packages" / "torch" / "share" / "cmake" / "Caffe2" / "public" / "cuda.cmake"
    if not cm.is_file():
        print(f"Not found: {cm}", file=sys.stderr)
        return 1
    text = cm.read_text(encoding="utf-8")
    marker = "Pix2Poly: also search CUDA toolkit include"
    if marker in text:
        print("Already patched.")
        return 0
    old = (
        'find_path(nvtx3_dir NAMES nvtx3 PATHS "${PROJECT_SOURCE_DIR}/third_party/NVTX/c/include" NO_DEFAULT_PATH)'
    )
    new = (
        f"# {marker} (torchmcubes has no bundled third_party/NVTX)\n"
        'find_path(nvtx3_dir NAMES nvtx3 PATHS "${PROJECT_SOURCE_DIR}/third_party/NVTX/c/include" '
        '"$ENV{CUDA_PATH}/include" NO_DEFAULT_PATH)'
    )
    if old not in text:
        print("Expected find_path(nvtx3...) line not found — PyTorch version may differ.", file=sys.stderr)
        return 1
    cm.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"Patched: {cm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
