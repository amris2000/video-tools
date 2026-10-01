from pydantic import BaseModel


class ConfigResponse(BaseModel):
    configured: bool
    projects_directory: str | None


class ConfigUpdate(BaseModel):
    projects_directory: str


class ProjectPathsResponse(BaseModel):
    clips: str
    metadata: str
    edits: str
    exports: str
    exports_social: str
    journal: str


class ProjectResponse(BaseModel):
    id: str
    name: str
    path: str
    timezone: str | None = None
    paths: ProjectPathsResponse


class ProjectStatsResponse(BaseModel):
    clips: int
    edits: int
    renders: int
    social_exports: int


class ProjectDetailsResponse(ProjectResponse):
    stats: ProjectStatsResponse
class ClipResponse(BaseModel):
    path: str
    name: str
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    creation_time: str | None = None
    thumbnail_url: str | None = None
