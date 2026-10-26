"""
Video URL → 3D pipeline.

Steps:
  1. Download video from URL (httpx streaming, size/duration limits)
  2. Extract frames with ffmpeg (subprocess)
  3. Run COLMAP SfM + MVS → point cloud → mesh (colmap_runner)
  4. Generate PBR maps from first representative frame
  5. Update job status with output paths

Environment variables:
  PIX2POLY_VIDEO_MAX_MB     – max video download size in MB (default: 500)
  PIX2POLY_VIDEO_FPS        – frame extraction rate (default: 2)
  PIX2POLY_VIDEO_MAX_FRAMES – max frames to use (default: 60)
  PIX2POLY_FFMPEG_PATH      – path to ffmpeg binary (default: ffmpeg on PATH)
"""
from __future__ import annotations

import asyncio

import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from uuid import UUID

import httpx

from app.schemas import JobStatus
from app.services.colmap_runner import colmap_available, run_colmap_pipeline
from app.services.fbx_exporter import export_to_fbx
from app.services.jobs import job_store
from app.services.mesh_from_image import mesh_from_image_file
from app.services.pbr_generator import generate_pbr_maps
from app.services.storage import OUTPUT_ROOT, UPLOAD_ROOT, ensure_output_dir

USER_AGENT = "Pix2Poly/0.1 (+https://github.com/HEO-J-H/Pix2Poly)"

_MAX_MB = int(os.environ.get("PIX2POLY_VIDEO_MAX_MB", "500"))
_FPS = float(os.environ.get("PIX2POLY_VIDEO_FPS", "2"))
_MAX_FRAMES = int(os.environ.get("PIX2POLY_VIDEO_MAX_FRAMES", "60"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ffmpeg_bin() -> str:
    env = os.environ.get("PIX2POLY_FFMPEG_PATH", "").strip()
    if env and Path(env).is_file():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise FileNotFoundError(
        "ffmpeg not found. Install FFmpeg and ensure it is on PATH, "
        "or set PIX2POLY_FFMPEG_PATH."
    )


def ffmpeg_available() -> bool:
    try:
        _ffmpeg_bin()
        return True
    except FileNotFoundError:
        return False


async def _download_video(url: str, dest: Path) -> None:
    """Stream-download a video URL to dest, enforcing size limit."""
    max_bytes = _MAX_MB * 1024 * 1024
    from app.services.url_ingest import check_public_url
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=False,
        timeout=httpx.Timeout(30.0, read=120.0),
    ) as client:
        for _ in range(6):  # 리다이렉트마다 공인 주소인지 다시 검사 (내부망 접근 차단)
            check_public_url(url)
            head = await client.head(url)
            if head.is_redirect and head.headers.get("location"):
                url = str(head.next_request.url) if head.next_request else head.headers["location"]
                continue
            break
        check_public_url(url)
        async with client.stream("GET", url) as r:
            r.raise_for_status()
            # Content-Length check
            cl = r.headers.get("content-length")
            if cl and int(cl) > max_bytes:
                raise ValueError(
                    f"Video file too large ({int(cl) // (1024*1024)} MB > {_MAX_MB} MB limit)"
                )
            received = 0
            with open(dest, "wb") as f:
                async for chunk in r.aiter_bytes(chunk_size=65536):
                    received += len(chunk)
                    if received > max_bytes:
                        raise ValueError(
                            f"Video exceeded {_MAX_MB} MB download limit."
                        )
                    f.write(chunk)


def _extract_frames(video_path: Path, frames_dir: Path) -> list[Path]:
    """Use ffmpeg to extract frames at _FPS fps, up to _MAX_FRAMES."""
    frames_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = _ffmpeg_bin()

    # First pass: extract at target FPS
    result = subprocess.run(
        [
            ffmpeg, "-y",
            "-i", str(video_path),
            "-vf", f"fps={_FPS}",
            "-q:v", "2",
            "-frames:v", str(_MAX_FRAMES),
            str(frames_dir / "frame_%04d.jpg"),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
    )
    if result.returncode != 0:
        err = result.stdout.decode(errors="replace")[-2000:]
        raise RuntimeError(f"ffmpeg frame extraction failed: {err}")

    frames = sorted(frames_dir.glob("frame_*.jpg"))
    if not frames:
        raise RuntimeError("ffmpeg produced no frames. Check video URL and format.")
    return frames[:_MAX_FRAMES]


# ---------------------------------------------------------------------------
# Main pipeline entry
# ---------------------------------------------------------------------------

async def build_video_job(job_id: UUID) -> None:
    """
    Background task: download video → frames → COLMAP (if available) or
    single-frame heightfield fallback → PBR → FBX.
    """
    await job_store.set_status(job_id, JobStatus.running, "Downloading video…")
    try:
        rec = await job_store.get(job_id)
        if not rec:
            return
        detail = rec.detail or {}
        video_url = detail.get("video_url")
        if not video_url:
            raise ValueError("No video_url in job detail")

        out_dir = ensure_output_dir(job_id)
        video_dir = UPLOAD_ROOT / str(job_id)
        video_dir.mkdir(parents=True, exist_ok=True)

        # 1. Download
        video_path = video_dir / "video.mp4"
        await _download_video(video_url, video_path)

        await job_store.set_status(job_id, JobStatus.running, "Extracting frames…")

        # 2. Extract frames
        if not ffmpeg_available():
            raise RuntimeError(
                "ffmpeg not found. Install FFmpeg (https://ffmpeg.org/download.html) "
                "and add to PATH, or set PIX2POLY_FFMPEG_PATH."
            )
        frames_dir = video_dir / "frames"
        frames = await asyncio.to_thread(_extract_frames, video_path, frames_dir)

        await job_store.set_status(
            job_id, JobStatus.running,
            f"Reconstructing 3D from {len(frames)} frames…"
        )

        backend_root = OUTPUT_ROOT.parent

        # 3. 3D reconstruction
        if colmap_available() and len(frames) >= 5:
            obj_abs, glb_abs = await asyncio.to_thread(run_colmap_pipeline, frames_dir, out_dir, sequential=True)
            method = "video_colmap_sfm"
            note = f"Video → {len(frames)} frames → COLMAP SfM+MVS → Poisson mesh."
            ok_msg = f"Mesh ready from video (COLMAP, {len(frames)} frames)."
        else:
            # Fallback: heightfield from middle frame
            mid = frames[len(frames) // 2]
            obj_abs, glb_abs = await asyncio.to_thread(mesh_from_image_file, mid, out_dir, grid=200, height_scale=0.45)
            method = "video_single_frame_heightfield"
            note = (
                f"Video → {len(frames)} frames extracted; COLMAP unavailable or too few frames. "
                "Used middle frame heightfield. Install COLMAP for full reconstruction."
            )
            ok_msg = "Mesh ready (single-frame heightfield fallback)."

        obj_rel = str(obj_abs.relative_to(backend_root)).replace("\\", "/")
        glb_rel = str(glb_abs.relative_to(backend_root)).replace("\\", "/")

        # 4. PBR maps from first frame
        pbr_detail: dict = {}
        try:
            rep_frame = frames[0]
            pbr_paths = await asyncio.to_thread(generate_pbr_maps, rep_frame, out_dir)
            pbr_detail = {
                k: str(v.relative_to(backend_root)).replace("\\", "/")
                for k, v in pbr_paths.items()
            }
        except Exception as _pbr_err:
            pbr_detail = {"error": str(_pbr_err)}

        # 5. FBX
        fbx_rel: str | None = None
        try:
            fbx_abs = export_to_fbx(glb_abs, out_dir)
            if fbx_abs and fbx_abs.exists():
                fbx_rel = str(fbx_abs.relative_to(backend_root)).replace("\\", "/")
        except Exception:
            pass

        output_paths = [obj_rel, glb_rel] + ([fbx_rel] if fbx_rel else [])
        formats = ["obj", "glb"] + (["fbx"] if fbx_rel else [])

        await job_store.set_status(
            job_id,
            JobStatus.succeeded,
            ok_msg,
            detail_update={
                "output_paths": output_paths,
                "pbr_paths": pbr_detail,
                "frames_count": len(frames),
                "formats": formats,
                "mesh_method": method,
                "note": note,
            },
        )
    except Exception as e:
        tb = traceback.format_exc()
        await job_store.set_status(
            job_id,
            JobStatus.failed,
            str(e) or "video pipeline failed",
            detail_update={"error_trace": tb[-4000:]},
        )
