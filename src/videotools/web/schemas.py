from pydantic import BaseModel


class ConfigResponse(BaseModel):
    configured: bool
    projects_directory: str | None


class ConfigUpdate(BaseModel):
    projects_directory: str


class ProjectPathsResponse(BaseModel):
    clips: str
    metadata: str
    exports: str
    journal: str


class ProjectResponse(BaseModel):
    id: str
    name: str
    path: str
    timezone: str | None = None
    paths: ProjectPathsResponse