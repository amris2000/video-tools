from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt


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


class ProjectCreateRequest(BaseModel):
    name: str


class JournalEntryCreateRequest(BaseModel):
    date: str
    activity: str
    location: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    tags: list[str] = Field(default_factory=list)
    highlight: str | None = None
    notes: str | None = None


class JournalEntryUpdateRequest(JournalEntryCreateRequest):
    pass


class JournalEntryResponse(BaseModel):
    id: str
    date: str
    activity: str
    location: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    tags: list[str] = Field(default_factory=list)
    highlight: str | None = None
    notes: str | None = None
    logged_at: str


class MaintenanceRunRequest(BaseModel):
    force: bool = False


class ClipJournalResponse(BaseModel):
    date: str | None = None
    activity: str | None = None
    location: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    tags: list[str] = Field(default_factory=list)
    highlight: str | None = None


class ClipGpsResponse(BaseModel):
    available: bool
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    speed: float | None = None
    datetime: str | None = None

class ClipResponse(BaseModel):
    path: str
    media_path: str
    name: str
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    creation_time: str | None = None
    thumbnail_url: str | None = None
    journal: ClipJournalResponse | None = None
    gps: ClipGpsResponse | None = None


class EditClipDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    start: StrictInt | StrictFloat
    end: StrictInt | StrictFloat
    label: str | None = None
    speed: StrictInt | StrictFloat | None = None


class EditDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: StrictInt = 1
    output: str
    clips: list[EditClipDocument]


class EditCreateRequest(BaseModel):
    filename: str | None = None
    output: str | None = None


class EditSaveRequest(BaseModel):
    document: EditDocument


class EditRenameRequest(BaseModel):
    filename: str


class EditSummaryResponse(BaseModel):
    filename: str
    clip_count: int | None


class EditResponse(BaseModel):
    filename: str
    document: EditDocument


class RenderRequest(BaseModel):
    edit_filename: str
    mode: Literal["accurate", "fast"]
    gpu: bool = False


class GpuEncoderInfo(BaseModel):
    key: str
    name: str
    codec: str


class GpuStatusResponse(BaseModel):
    available: bool
    encoder: GpuEncoderInfo | None
    reason: str | None


class SocialExportRequest(BaseModel):
    source_filename: str
    preset: str
    framing: Literal["crop", "fit"]


class MediaJobResponse(BaseModel):
    job_id: str
    project_id: str
    kind: str
    status: Literal["queued", "running", "completed", "failed"]
    output_filename: str | None = None
    error: str | None = None
    progress: dict[str, Any] | None = None
    result: dict[str, Any] | None = None


class ExportEntryResponse(BaseModel):
    filename: str
    category: Literal["render", "social"]
    size_bytes: int
    modified_at: str
    url: str


class ExportsResponse(BaseModel):
    renders: list[ExportEntryResponse]
    social_exports: list[ExportEntryResponse]


class SocialPresetResponse(BaseModel):
    key: str
    name: str
    description: str


class FramingModeResponse(BaseModel):
    key: Literal["crop", "fit"]
    name: str


class SocialOptionsResponse(BaseModel):
    presets: list[SocialPresetResponse]
    framing_modes: list[FramingModeResponse]


class ImportScanRequest(BaseModel):
    source_path: str


class ImportFileResponse(BaseModel):
    source_relative_path: str
    filename: str
    size_bytes: int
    status: Literal["new", "already_imported", "conflict"]


class ImportPlanResponse(BaseModel):
    source: str
    total_source_files: int
    already_imported: int
    new_files: int
    conflicts: int
    files: list[ImportFileResponse]


class ImportExecuteRequest(ImportScanRequest):
    selected_paths: list[str]


class ImportResultResponse(BaseModel):
    imported: int
    skipped: int
    conflicts: int
    errors: list[str]


class DetectedImportSourceResponse(BaseModel):
    path: str
    label: str
    source_type: Literal["gopro", "gopro_usb"]
    reason: str
