from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

from app.schemas import JobResponse, JobStatus, JobType, UrlIngestResponse, UrlJobCreate
from app.services.jobs import JobRecord, job_store
from app.services.storage import save_job_files
from app.services.url_ingest import fetch_page_image_candidates

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
    file: UploadFile = File(...),
    notes: Optional[str] = Form(None),
) -> JobResponse:
    rec = await job_store.create(JobType.single_image, detail={})
    raw = await file.read()
    upload_paths = save_job_files(rec.job_id, [(file.filename, raw)])
    await job_store.set_status(
        rec.job_id,
        JobStatus.queued,
        "Awaiting worker integration",
        detail_update={
            "filename": file.filename,
            "content_type": file.content_type,
            "notes": notes,
            "upload_paths": upload_paths,
            "pipeline": "pending: single-image 3D + PBR + mesh optimize",
        },
    )
    return _to_response(rec)


@app.post("/v1/jobs/multi-image", response_model=JobResponse)
async def create_multi_image_job(
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
        "Awaiting worker integration",
        detail_update={
            "count": len(files),
            "filenames": [f.filename for f in files],
            "notes": notes,
            "upload_paths": upload_paths,
            "pipeline": "pending: multi-view 3D + PBR + mesh optimize",
        },
    )
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


_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=str(_STATIC_DIR), html=True), name="ui")


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/ui/")
