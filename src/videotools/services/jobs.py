from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Callable
from uuid import uuid4


class JobInProgressError(RuntimeError):
    """Raised when another media operation is already active."""


@dataclass
class MediaJob:
    job_id: str
    project_id: str
    kind: str
    status: str = "queued"
    output_filename: str | None = None
    error: str | None = None


_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="video-tools-media")
_lock = RLock()
_jobs: dict[str, MediaJob] = {}


def start_job(
    project_id: str,
    kind: str,
    action: Callable[[], Path],
) -> MediaJob:
    with _lock:
        if any(
            job.status in {"queued", "running"}
            for job in _jobs.values()
        ):
            raise JobInProgressError("Another media operation is already in progress.")

        job = MediaJob(job_id=uuid4().hex, project_id=project_id, kind=kind)
        _jobs[job.job_id] = job
        _executor.submit(_run_job, job.job_id, action)
        return _copy_job(job)


def get_job(project_id: str, job_id: str) -> MediaJob | None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None or job.project_id != project_id:
            return None
        return _copy_job(job)


def _run_job(job_id: str, action: Callable[[], Path]) -> None:
    with _lock:
        job = _jobs[job_id]
        job.status = "running"

    try:
        output = action()
    except Exception as error:
        with _lock:
            job.status = "failed"
            job.error = str(error) or error.__class__.__name__
    else:
        with _lock:
            job.status = "completed"
            job.output_filename = output.name


def _copy_job(job: MediaJob) -> MediaJob:
    return MediaJob(
        job_id=job.job_id,
        project_id=job.project_id,
        kind=job.kind,
        status=job.status,
        output_filename=job.output_filename,
        error=job.error,
    )
