from __future__ import annotations

from dataclasses import asdict
import mimetypes
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from videotools.edit import EditValidationError
from videotools.project import VideoProject
from videotools.services.edits import (
    create_edit,
    delete_edit,
    get_edit,
    list_edits,
    rename_edit,
    save_edit,
)
from videotools.services.jobs import JobInProgressError, get_job
from videotools.services.media import (
    parse_byte_range,
    resolve_export_video,
    resolve_project_media,
    stream_file,
)
from videotools.services.workflows import (
    list_exports,
    social_options,
    start_render,
    start_social_export,
)
from videotools.services.projects import get_project
from videotools.web.schemas import (
    EditCreateRequest,
    EditDocument,
    EditRenameRequest,
    EditResponse,
    EditSaveRequest,
    EditSummaryResponse,
    ExportsResponse,
    MediaJobResponse,
    RenderRequest,
    SocialExportRequest,
    SocialOptionsResponse,
)

router = APIRouter(prefix="/projects", tags=["project workflows"])


def _project(project_id: str) -> VideoProject:
    if project_id in {".", ".."} or any(character in project_id for character in "/\\:"):
        raise HTTPException(status_code=404, detail="Project not found.")
    try:
        info = get_project(project_id)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if info is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return VideoProject.load(info.path)


def _raise_service_error(error: Exception) -> None:
    if isinstance(error, FileExistsError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    if isinstance(error, FileNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, (ValueError, EditValidationError)):
        raise HTTPException(status_code=400, detail=str(error)) from error
    if isinstance(error, JobInProgressError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    if isinstance(error, RuntimeError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    raise error


def _job_response(job) -> MediaJobResponse:
    return MediaJobResponse(**asdict(job))


@router.get("/{project_id}/edits", response_model=list[EditSummaryResponse])
def get_edits(project_id: str) -> list[dict]:
    return list_edits(_project(project_id))


@router.post("/{project_id}/edits", response_model=EditResponse, status_code=201)
def post_edit(project_id: str, request: EditCreateRequest) -> dict:
    project = _project(project_id)
    try:
        filename, document = create_edit(project, request.filename, request.output)
    except Exception as error:
        _raise_service_error(error)
    return {"filename": filename, "document": document}


@router.get("/{project_id}/edits/{filename}", response_model=EditDocument)
def get_edit_document(project_id: str, filename: str) -> dict:
    try:
        return get_edit(_project(project_id), filename)
    except Exception as error:
        _raise_service_error(error)


@router.put("/{project_id}/edits/{filename}", response_model=EditResponse)
def put_edit(project_id: str, filename: str, request: EditSaveRequest) -> dict:
    try:
        document = save_edit(_project(project_id), filename, request.document.model_dump())
    except Exception as error:
        _raise_service_error(error)
    return {"filename": filename, "document": document}


@router.post("/{project_id}/edits/{filename}/rename")
def post_edit_rename(
    project_id: str,
    filename: str,
    request: EditRenameRequest,
) -> dict[str, str]:
    try:
        renamed = rename_edit(_project(project_id), filename, request.filename)
    except Exception as error:
        _raise_service_error(error)
    return {"filename": renamed}


@router.delete("/{project_id}/edits/{filename}", status_code=204)
def remove_edit(project_id: str, filename: str) -> Response:
    try:
        delete_edit(_project(project_id), filename)
    except Exception as error:
        _raise_service_error(error)
    return Response(status_code=204)


@router.get("/{project_id}/media/{relative_path:path}")
def get_project_media(
    project_id: str,
    relative_path: str,
    request: Request,
):
    try:
        path = resolve_project_media(_project(project_id), relative_path)
    except Exception as error:
        _raise_service_error(error)
    return _stream_response(path, request.headers.get("range"))


@router.get("/{project_id}/exports", response_model=ExportsResponse)
def get_project_exports(project_id: str) -> dict:
    return list_exports(_project(project_id), quote(project_id, safe=""))


@router.get("/{project_id}/exports/{filename}")
def get_export_media(project_id: str, filename: str, request: Request):
    try:
        path = resolve_export_video(_project(project_id), filename)
    except Exception as error:
        _raise_service_error(error)
    return _stream_response(path, request.headers.get("range"))


@router.get("/{project_id}/social-exports/{filename}")
def get_social_export_media(project_id: str, filename: str, request: Request):
    try:
        path = resolve_export_video(_project(project_id), filename, social=True)
    except Exception as error:
        _raise_service_error(error)
    return _stream_response(path, request.headers.get("range"))


@router.get("/{project_id}/social-options", response_model=SocialOptionsResponse)
def get_social_options(project_id: str) -> dict:
    _project(project_id)
    return social_options()


@router.post("/{project_id}/renders", response_model=MediaJobResponse, status_code=202)
def post_render(project_id: str, request: RenderRequest) -> MediaJobResponse:
    try:
        job = start_render(_project(project_id), project_id, request.edit_filename, request.mode)
    except Exception as error:
        _raise_service_error(error)
    return _job_response(job)


@router.post("/{project_id}/social-exports", response_model=MediaJobResponse, status_code=202)
def post_social_export(
    project_id: str,
    request: SocialExportRequest,
) -> MediaJobResponse:
    try:
        job = start_social_export(
            _project(project_id),
            project_id,
            request.source_filename,
            request.preset,
            request.framing,
        )
    except Exception as error:
        _raise_service_error(error)
    return _job_response(job)


@router.get("/{project_id}/jobs/{job_id}", response_model=MediaJobResponse)
def get_project_job(project_id: str, job_id: str) -> MediaJobResponse:
    _project(project_id)
    job = get_job(project_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Media job not found.")
    return _job_response(job)


def _stream_response(path, range_header: str | None):
    file_size = path.stat().st_size
    content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    headers = {"Accept-Ranges": "bytes"}

    if range_header:
        start, end = parse_byte_range(range_header, file_size)
        if start is None or end is None:
            return Response(
                status_code=416,
                headers={**headers, "Content-Range": f"bytes */{file_size}"},
            )
        length = end - start + 1
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        headers["Content-Length"] = str(length)
        return StreamingResponse(
            stream_file(path, start=start, length=length),
            status_code=206,
            media_type=content_type,
            headers=headers,
        )

    headers["Content-Length"] = str(file_size)
    return StreamingResponse(
        stream_file(path, start=0, length=file_size),
        media_type=content_type,
        headers=headers,
    )
