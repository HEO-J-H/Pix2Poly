from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import httpx
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import RedirectResponse

from app.schemas import (
    JobResponse,
    JobStatus,
    JobType,
    UrlIngestResponse,
    UrlJobCreate,
    VideoUrlJobCreate,
)
from app.services.jobs import JobRecord, job_store
from app.services.mesh_worker import build_mesh_for_image_job
from app.services.storage import OUTPUT_ROOT, UPLOAD_ROOT, save_job_files
from app.services.url_ingest import USER_AGENT, fetch_page_image_candidates
from app.services.video_pipeline import build_video_job

app = FastAPI(
    title="Pix2Poly API",
    description="URL / image 기반 3D·PBR 파이프라인 오케스트레이션 API (MVP)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


def _to_response(rec: JobRecord) -> JobResponse:
    return JobResponse(
        job_id=rec.job_id,
        type=rec.type,
        status=rec.status,
        message=rec.message,
        detail=rec.detail or None,
    )


@app.post("/v1/jobs/single-image", response_model=JobResponse)
async def create_single_image_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    notes: Optional[str] = Form(None),
) -> JobResponse:
    rec = await job_store.create(JobType.single_image, detail={})
    raw = await file.read()
    upload_paths = save_job_files(rec.job_id, [(file.filename, raw)])
    await job_store.set_status(
        rec.job_id,
        JobStatus.queued,
        "Queued: mesh generation (OBJ/GLB)",
        detail_update={
            "filename": file.filename,
            "content_type": file.content_type,
            "notes": notes,
            "upload_paths": upload_paths,
            "pipeline": "single-image → heightfield mesh → outputs/model.obj + model.glb",
        },
    )
    background_tasks.add_task(build_mesh_for_image_job, rec.job_id)
    return _to_response(rec)


@app.post("/v1/jobs/multi-image", response_model=JobResponse)
async def create_multi_image_job(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    min_images: int = Form(2),
    notes: Optional[str] = Form(None),
) -> JobResponse:
    if len(files) < min_images:
        raise HTTPException(
            status_code=400,
            detail=f"At least {min_images} images required, got {len(files)}",
        )
    rec = await job_store.create(JobType.multi_image, detail={})
    pairs: List[Tuple[Optional[str], bytes]] = []
    for uf in files:
        pairs.append((uf.filename, await uf.read()))
    upload_paths = save_job_files(rec.job_id, pairs)
    await job_store.set_status(
        rec.job_id,
        JobStatus.queued,
        "Queued: mesh from first image (OBJ/GLB)",
        detail_update={
            "count": len(files),
            "filenames": [f.filename for f in files],
            "notes": notes,
            "upload_paths": upload_paths,
            "pipeline": "multi-image → first image heightfield → outputs/model.obj + model.glb",
        },
    )
    background_tasks.add_task(build_mesh_for_image_job, rec.job_id)
    return _to_response(rec)


@app.post("/v1/jobs/video-url", response_model=JobResponse)
async def create_video_url_job(
    background_tasks: BackgroundTasks,
    body: VideoUrlJobCreate,
) -> JobResponse:
    """Download video from URL, extract frames, run COLMAP or heightfield fallback."""
    vurl = str(body.video_url)
    rec = await job_store.create(
        JobType.video_url,
        detail={
            "video_url": vurl,
            "notes": body.notes,
            "pipeline_hint": body.pipeline_hint,
            "pipeline": (
                "video URL → ffmpeg frames → COLMAP SfM+MVS (if available) "
                "or middle-frame heightfield fallback → OBJ/GLB + PBR"
            ),
        },
    )
    await job_store.set_status(
        rec.job_id,
        JobStatus.queued,
        "Queued: downloading video and running 3D reconstruction",
    )
    background_tasks.add_task(build_video_job, rec.job_id)
    return _to_response(rec)


@app.post("/v1/jobs/url", response_model=JobResponse)
async def create_url_job(body: UrlJobCreate) -> JobResponse:
    page = str(body.page_url)
    candidates, robots_ok, truncated = await fetch_page_image_candidates(
        page,
        max_candidates=body.max_candidates,
    )
    rec = await job_store.create(
        JobType.url,
        detail={
            "page_url": page,
            "robots_allowed": robots_ok,
            "image_candidates": candidates,
            "candidates_truncated": truncated,
            "pipeline": "pending: user selection + single/multi pipeline",
        },
    )
    if robots_ok is False:
        await job_store.set_status(
            rec.job_id,
            JobStatus.failed,
            "robots.txt disallows fetching this URL",
        )
    else:
        await job_store.set_status(rec.job_id, JobStatus.queued, "Awaiting worker integration")
    return _to_response(rec)


class UrlImagesJobCreate(BaseModel):
    """Select image URLs from a previous ingest and create a 3D mesh job."""
    selected_urls: List[str]
    notes: Optional[str] = None


@app.post("/v1/jobs/url-images", response_model=JobResponse)
async def create_url_images_job(
    background_tasks: BackgroundTasks,
    body: UrlImagesJobCreate,
) -> JobResponse:
    """Download selected image URLs and queue a mesh-generation job."""
    if not body.selected_urls:
        raise HTTPException(status_code=400, detail="selected_urls must not be empty")

    rec = await job_store.create(JobType.url, detail={})

    # Download each selected image
    downloaded: List[Tuple[Optional[str], bytes]] = []
    failed_urls: List[str] = []
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=30.0,
    ) as client:
        for url in body.selected_urls[:10]:  # max 10 images
            try:
                r = await client.get(url)
                r.raise_for_status()
                ct = r.headers.get("content-type", "")
                if not ct.startswith("image/"):
                    continue
                ext = ct.split("/")[-1].split(";")[0].strip() or "jpg"
                fname = url.split("/")[-1].split("?")[0] or f"image.{ext}"
                downloaded.append((fname, r.content))
            except Exception:
                failed_urls.append(url)

    if not downloaded:
        await job_store.set_status(
            rec.job_id,
            JobStatus.failed,
            "No images could be downloaded from the provided URLs",
        )
        return _to_response(rec)

    upload_paths = save_job_files(rec.job_id, downloaded)
    await job_store.set_status(
        rec.job_id,
        JobStatus.queued,
        "Queued: mesh from downloaded URL images",
        detail_update={
            "selected_urls": body.selected_urls,
            "failed_urls": failed_urls,
            "upload_paths": upload_paths,
            "notes": body.notes,
            "pipeline": "url-images → download → heightfield/TripoSR mesh → OBJ/GLB + PBR",
        },
    )
    background_tasks.add_task(build_mesh_for_image_job, rec.job_id)
    return _to_response(rec)


@app.post("/v1/ingest/url", response_model=UrlIngestResponse)
async def ingest_url_only(body: UrlJobCreate) -> UrlIngestResponse:
    """Preview image URLs from a page without creating a job."""
    page = str(body.page_url)
    candidates, robots_ok, truncated = await fetch_page_image_candidates(
        page,
        max_candidates=body.max_candidates,
    )
    return UrlIngestResponse(
        page_url=page,
        robots_allowed=robots_ok,
        candidates=candidates,
        truncated=truncated,
    )


@app.get("/v1/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID) -> JobResponse:
    rec = await job_store.get(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_response(rec)


UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_ROOT)), name="uploads")
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_ROOT)), name="outputs")

_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/ui", StaticFiles(directory=str(_static_dir), html=True), name="ui")


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/ui/")
