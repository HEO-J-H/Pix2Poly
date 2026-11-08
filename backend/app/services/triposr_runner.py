"""
Run TripoSR (external repo) via subprocess. Requires separate venv with PyTorch + TripoSR deps.

Official: https://github.com/VAST-AI-Research/TripoSR
Typical: python run.py <image> --output-dir <dir> [--model-save-format obj|glb]
Output layout: <output-dir>/0/mesh.obj (and optionally mesh.glb)
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import trimesh


def run_triposr_to_output_dir(
    image_path: Path,
    job_output_dir: Path,
    triposr_root: Path,
    python_exe: str,
    timeout_s: int = 900,
    device: Optional[str] = None,
) -> Tuple[Path, Path]:
    """
    Execute TripoSR run.py into a temp dir, then copy mesh to job_output_dir as model.obj / model.glb.
    """
    run_py = triposr_root / "run.py"
    if not run_py.is_file():
        raise FileNotFoundError(f"TripoSR run.py not found: {run_py}")

    image_path = image_path.resolve()
    job_output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="triposr_") as tmp:
        tmp_path = Path(tmp)
        cmd = [
            python_exe,
            str(run_py),
            str(image_path),
            "--output-dir",
            str(tmp_path),
            "--model-save-format",
            "obj",
        ]
        if device:
            cmd.extend(["--device", device])
        try:
            subprocess.run(
                cmd,
                cwd=str(triposr_root),
                check=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"TripoSR 가 {timeout_s}초 안에 끝나지 않았습니다 — GPU 가 없거나 VRAM(약 6GB 권장)이 부족할 수 있습니다") from e
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"TripoSR 실행 실패 (종료 코드 {e.returncode}) — 워커 콘솔의 GPU/CUDA 로그를 확인하세요") from e
        except OSError as e:
            raise RuntimeError(f"TripoSR 를 실행할 파이썬을 찾지 못했습니다 ({python_exe}): {e}") from e

        sub = tmp_path / "0"
        src_obj = sub / "mesh.obj"
        if not src_obj.is_file():
            raise RuntimeError(
                f"TripoSR did not produce {sub}/mesh.obj. Check GPU/CUDA logs in worker console."
            )

        dest_obj = job_output_dir / "model.obj"
        dest_glb = job_output_dir / "model.glb"
        shutil.copy2(src_obj, dest_obj)

        src_glb = sub / "mesh.glb"
        if src_glb.is_file():
            shutil.copy2(src_glb, dest_glb)
        else:
            mesh = trimesh.load(str(dest_obj), force="mesh")
            mesh.export(str(dest_glb))

        return dest_obj, dest_glb
