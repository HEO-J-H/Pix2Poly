from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from app.schemas import JobStatus, JobType


@dataclass
class JobRecord:
    job_id: UUID
    type: JobType
    status: JobStatus
    message: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


class JobStore:
    """In-memory job store for MVP; replace with DB + queue in production."""

    def __init__(self) -> None:
        self._jobs: dict[UUID, JobRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, job_type: JobType, detail: dict[str, Any] | None = None) -> JobRecord:
        async with self._lock:
            jid = uuid4()
            rec = JobRecord(job_id=jid, type=job_type, status=JobStatus.queued, detail=detail or {})
            self._jobs[jid] = rec
            return rec

    async def get(self, job_id: UUID) -> JobRecord | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def set_status(
        self,
        job_id: UUID,
        status: JobStatus,
        message: str | None = None,
        detail_update: dict[str, Any] | None = None,
    ) -> None:
        async with self._lock:
            rec = self._jobs.get(job_id)
            if not rec:
                return
            rec.status = status
            if message is not None:
                rec.message = message
            if detail_update:
                rec.detail.update(detail_update)


job_store = JobStore()
