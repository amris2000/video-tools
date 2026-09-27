from fastapi import APIRouter, HTTPException

from videotools.services.projects import (
    ProjectInfo,
    calculate_project_stats,
    discover_projects,
    get_project,
)
from videotools.web.schemas import (
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