"""
GPU worker / mesh backend configuration (env vars).

- PIX2POLY_MESH_BACKEND: heightfield | triposr | instantmesh | colmap (default: heightfield)
- PIX2POLY_TRIPOSR_REPO_PATH: absolute path to cloned VAST-AI-Research/TripoSR
- PIX2POLY_TRIPOSR_PYTHON: python exe for TripoSR env (must have torch, etc.)
- PIX2POLY_TRIPOSR_DEVICE: optional, e.g. cuda:0 or cpu (passed to TripoSR run.py --device)
- PIX2POLY_INSTANTMESH_REPO_PATH / PIX2POLY_INSTANTMESH_PYTHON: same idea for InstantMesh
- PIX2POLY_COLMAP_PATH: absolute path to colmap binary (default: colmap on PATH)
- PIX2POLY_COLMAP_GPU: 1 to enable GPU feature extraction/matching (default: 0)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def mesh_backend() -> str:
    v = (os.getenv("PIX2POLY_MESH_BACKEND") or "heightfield").strip().lower()
    if v not in ("heightfield", "triposr", "instantmesh", "colmap"):
        return "heightfield"
    return v


def triposr_repo_path() -> Optional[Path]:
    p = os.getenv("PIX2POLY_TRIPOSR_REPO_PATH") or os.getenv("TRIPOSR_REPO_PATH")
    if not p:
        return None
    return Path(p).expanduser().resolve()


def triposr_python() -> str:
    return os.getenv("PIX2POLY_TRIPOSR_PYTHON") or "python"


def triposr_device() -> Optional[str]:
    """e.g. cuda:0, cpu — forwarded to TripoSR run.py --device. Empty/unset = omit flag (TripoSR default)."""
    v = (os.getenv("PIX2POLY_TRIPOSR_DEVICE") or os.getenv("TRIPOSR_DEVICE") or "").strip()
    return v if v else None


def instantmesh_repo_path() -> Optional[Path]:
    p = os.getenv("PIX2POLY_INSTANTMESH_REPO_PATH")
    if not p:
        return None
    return Path(p).expanduser().resolve()


def instantmesh_python() -> str:
    return os.getenv("PIX2POLY_INSTANTMESH_PYTHON") or "python"


def instantmesh_config() -> str:
    return os.getenv("PIX2POLY_INSTANTMESH_CONFIG") or "configs/instant-mesh-large.yaml"
