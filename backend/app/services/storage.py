from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple
from uuid import UUID

# backend/app/services/storage.py -> parents: services, app, backend
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_ROOT = _BACKEND_ROOT / "uploads"
OUTPUT_ROOT = _BACKEND_ROOT / "outputs"

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._\-]+")


def _sanitize_filename(name: str | None) -> str:
    if not name:
        return "upload.bin"
    base = Path(name).name
    cleaned = _SAFE_NAME.sub("_", base).strip("._") or "upload.bin"
    return cleaned[:200]


def ensure_job_upload_dir(job_id: UUID) -> Path:
    d = UPLOAD_ROOT / str(job_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_output_dir(job_id: UUID) -> Path:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    d = OUTPUT_ROOT / str(job_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_job_files(job_id: UUID, files: List[Tuple[Optional[str], bytes]]) -> List[str]:
    """
    Write uploaded bytes under uploads/{job_id}/.
    Returns paths relative to backend root (e.g. uploads/<uuid>/photo.png).
    """
    ensure_job_upload_dir(job_id)
    rel_paths: List[str] = []
    for i, (filename, data) in enumerate(files):
        name = _sanitize_filename(filename)
        if len(files) > 1:
            name = f"{i:02d}_{name}"
        dest = UPLOAD_ROOT / str(job_id) / name
        dest.write_bytes(data)
        rel_paths.append(str(dest.relative_to(_BACKEND_ROOT)).replace("\\", "/"))
    return rel_paths
