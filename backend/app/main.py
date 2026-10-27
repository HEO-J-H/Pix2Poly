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
from app.services.url_ingest import safe_get, USER_AGENT, fetch_page_image_candidates
from app.services.video_pipeline import build_video_job

app = FastAPI(
    title="Pix2Poly API",
    description="URL / image 기반 3D·PBR 파이프라인 오케스트레이션 API (MVP)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    # 아무 웹사이트나 이 PC 의 API 를 호출하지 못하게 — 로컬 화면과 공개 웹 버전만
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000", "https://heo-j-h.github.io"],
    allow_origin_regex=r"http://(127\.0\.0\.1|localhost):\d+",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


MAX_IMAGE_BYTES = 50 * 1024 * 1024   # 장당 50MB
MAX_FILES = 200


async def _read_limited(uf: UploadFile) -> bytes:
    """업로드를 조금씩 읽어 장당 상한을 넘으면 413 (한 번에 메모리로 올리지 않음)."""
    buf = bytearray()
    while chunk := await uf.read(1024 * 1024):
        buf += chunk
        if len(buf) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail=f"{uf.filename}: 파일이 너무 큽니다 (장당 50MB 까지)")
    return bytes(buf)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/capabilities")
async def capabilities() -> Dict[str, object]:
    """이 PC 에서 쓸 수 있는 기능 — 화면이 '여러 장' 안내(COLMAP 설치·GPU 여부)에 사용."""
    from app.services.colmap_runner import colmap_available, colmap_has_cuda
    from app.services.mesh_worker import MIN_COLMAP_IMAGES
    has = colmap_available()
    from app.services import bg_remove
    from app.services.colmap_runner import openmvs_available
    return {"colmap": has, "colmap_gpu": has and colmap_has_cuda(), "min_colmap_images": MIN_COLMAP_IMAGES,
            "openmvs": openmvs_available(), "remove_bg": bg_remove.available(), "noface3d": False}


@app.get("/v1/engines")
async def list_engines() -> List[Dict[str, object]]:
    """사용 가능한 3D/미세 기하학 파이프라인 엔진 목록 제공."""
    from app.services.colmap_runner import colmap_available
    from app.services import bg_remove
    return [
        {"name": "heightfield", "available": True, "description": "단일 이미지 높이맵 기반 기본 CPU 메시/PBR 파이프라인"},
        {"name": "colmap", "available": colmap_available(), "description": "다중 이미지/영상 SfM+MVS 재구성"},
        {"name": "noface3d", "available": False, "description": "NOFACE3D 미세 세부 형상 보완 선택 엔진 (외부 워커 연동 검토)"},
        {"name": "remove_bg", "available": bg_remove.available(), "description": "rembg 기반 배경 제거"}
    ]


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
    remove_bg: bool = Form(False),
) -> JobResponse:
    rec = await job_store.create(JobType.single_image, detail={})
    raw = await _read_limited(file)
    upload_paths = save_job_files(rec.job_id, [(file.filename, raw)])
    await job_store.set_status(
        rec.job_id,
        JobStatus.queued,
        "Queued: mesh generation (OBJ/GLB)",
        detail_update={
            "filename": file.filename,
            "content_type": file.content_type,
            "notes": notes,
            "remove_bg": remove_bg,
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
    remove_bg: bool = Form(False),
) -> JobResponse:
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=413, detail=f"사진은 한 번에 {MAX_FILES}장까지")
    if len(files) < max(2, min_images):
        raise HTTPException(
            status_code=400,
            detail=f"At least {min_images} images required, got {len(files)}",
        )
    rec = await job_store.create(JobType.multi_image, detail={})
    pairs: List[Tuple[Optional[str], bytes]] = []
    for uf in files:
        pairs.append((uf.filename, await _read_limited(uf)))
    upload_paths = save_job_files(rec.job_id, pairs)
    await job_store.set_status(
        rec.job_id,
        JobStatus.queued,
        "Queued: mesh from first image (OBJ/GLB)",
        detail_update={
            "count": len(files),
            "filenames": [f.filename for f in files],
            "notes": notes,
            "remove_bg": remove_bg,
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
        follow_redirects=False,
        timeout=30.0,
    ) as client:
        for url in body.selected_urls[:10]:  # max 10 images
            try:
                r = await safe_get(client, url, MAX_IMAGE_BYTES)
                ct = r.headers.get("content-type", "")
                if not ct.startswith("image/"):
                    failed_urls.append(url)
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
