from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class JobType(str, Enum):
    single_image = "single_image"
    multi_image = "multi_image"
    url = "url"
    video_url = "video_url"


class SingleImageJobCreate(BaseModel):
    """Placeholder for file upload metadata; actual file sent as multipart."""

    notes: Optional[str] = None


class MultiImageJobCreate(BaseModel):
    min_images: int = Field(default=2, ge=2)
    notes: Optional[str] = None


class UrlJobCreate(BaseModel):
    page_url: HttpUrl
    max_candidates: int = Field(default=50, ge=1, le=200)


class VideoUrlJobCreate(BaseModel):
    """Video page URL or direct media URL; worker will ingest frames then reconstruct."""

    video_url: HttpUrl
    notes: Optional[str] = None
    pipeline_hint: str = Field(
        default="auto",
        description="auto | colmap_frames | neural_monocular",
    )


class JobResponse(BaseModel):
    job_id: UUID
    type: JobType
    status: JobStatus
    message: Optional[str] = None
    detail: Optional[dict[str, Any]] = None


class UrlIngestResponse(BaseModel):
    page_url: str
    robots_allowed: Optional[bool]
    candidates: List[str]
    truncated: bool
