from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from videotools.project import VideoProject
from videotools.services.clips import list_clips, resolve_thumbnail

from videotools.services.projects import (
    ProjectInfo,
    calculate_project_stats,
    create_project_in_projects_directory,
    delete_project_from_projects_directory,
    discover_projects,
    get_project,
)
from videotools.web.schemas import (
    ClipResponse,
    ProjectCreateRequest,
    ProjectDetailsResponse,
    ProjectPathsResponse,
    ProjectResponse,
    ProjectStatsResponse,
)


router = APIRouter(
    prefix="/projects",
    tags=["projects"],
)


def project_response(
    project: ProjectInfo,
) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        path=str(project.path),
        timezone=project.timezone,
        paths=ProjectPathsResponse(
            clips=project.paths.clips,
            metadata=project.paths.metadata,
            edits=project.paths.edits,
            exports=project.paths.exports,
            exports_social=(
                project.paths.exports_social
            ),
            journal=project.paths.journal,
        ),
    )


@router.get(
    "",
    response_model=list[ProjectResponse],
)
def get_projects() -> list[ProjectResponse]:
    try:
        projects = discover_projects()
    except RuntimeError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

    return [
        project_response(project)
        for project in projects
    ]


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=201,
)
def create_project_endpoint(
    request: ProjectCreateRequest,
) -> ProjectResponse:
    try:
        project = create_project_in_projects_directory(
            request.name
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except FileExistsError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

    return project_response(project)


@router.delete(
    "/{project_id}",
    status_code=204,
)
def delete_project_endpoint(
    project_id: str,
) -> None:
    try:
        delete_project_from_projects_directory(
            project_id
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error


@router.get(
    "/{project_id}",
    response_model=ProjectDetailsResponse,
)
def get_project_details(
    project_id: str,
) -> ProjectDetailsResponse:
    try:
        project = get_project(project_id)
    except RuntimeError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found.",
        )

    stats = calculate_project_stats(project)

    base = project_response(project)

    return ProjectDetailsResponse(
        **base.model_dump(),
        stats=ProjectStatsResponse(
            clips=stats.clips,
            edits=stats.edits,
            renders=stats.renders,
            social_exports=(
                stats.social_exports
            ),
        ),
    )

def _clip_project(project_id: str) -> VideoProject:
    if project_id in {".", ".."} or any(c in project_id for c in "/\\:"):
        raise HTTPException(status_code=404, detail="Project not found.")
    try:
        info = get_project(project_id)
        if info is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        return VideoProject.load(info.path)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{project_id}/clips", response_model=list[ClipResponse])
def get_clips(project_id: str) -> list[dict]:
    try:
        return list_clips(_clip_project(project_id), project_id)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{project_id}/thumbnails/{relative_path:path}")
def get_thumbnail(project_id: str, relative_path: str):
    try:
        return FileResponse(resolve_thumbnail(_clip_project(project_id), relative_path))
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=404, detail="Thumbnail not found.") from error
