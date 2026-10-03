import { api } from "./client";

export interface EditClipDocument {
  file: string;
  start: number;
  end: number;
  label?: string;
}

export interface EditDocument {
  version: 1;
  output: string;
  clips: EditClipDocument[];
}

export interface EditSummary {
  filename: string;
  clip_count: number | null;
}

export interface EditResponse {
  filename: string;
  document: EditDocument;
}

export interface MediaJob {
  job_id: string;
  project_id: string;
  kind: "render" | "social_export" | "import" | "probe" | "thumbnails";
  status: "queued" | "running" | "completed" | "failed";
  output_filename: string | null;
  error: string | null;
  progress?: ImportJobProgress | null;
  result?: ImportResult | null;
}

export interface ImportStageProgress {
  status: "waiting" | "running" | "completed" | "failed";
  current_file: string | null;
  completed: number;
  total: number;
  errors: string[];
}

export interface ImportJobProgress {
  stage: "import" | "thumbnails" | "probe" | null;
  stages: {
    import: ImportStageProgress;
    thumbnails: ImportStageProgress;
    probe: ImportStageProgress;
  };
}

export interface ExportFile {
  filename: string;
  category: "render" | "social";
  size_bytes: number;
  modified_at: string;
  url: string;
}

export interface ProjectExports {
  renders: ExportFile[];
  social_exports: ExportFile[];
}

export interface SocialOptions {
  presets: { key: string; name: string; description: string }[];
  framing_modes: { key: "crop" | "fit"; name: string }[];
}

export interface JournalEntryPayload {
  date: string;
  activity: string;
  location: string | null;
  start_time: string | null;
  end_time: string | null;
  tags: string[];
  highlight: string | null;
  notes: string | null;
}

export interface JournalEntry extends JournalEntryPayload {
  id: string;
  logged_at: string;
}

const projectPath = (projectId: string) =>
  `/api/projects/${encodeURIComponent(projectId)}`;

export function getEdits(projectId: string, signal?: AbortSignal) {
  return api<EditSummary[]>(`${projectPath(projectId)}/edits`, { signal });
}

export function getEdit(projectId: string, filename: string) {
  return api<EditDocument>(
    `${projectPath(projectId)}/edits/${encodeURIComponent(filename)}`,
  );
}

export function createEdit(projectId: string, filename?: string) {
  return api<EditResponse>(`${projectPath(projectId)}/edits`, {
    method: "POST",
    body: JSON.stringify({ filename }),
  });
}

export function saveEdit(
  projectId: string,
  filename: string,
  document: EditDocument,
) {
  return api<EditResponse>(
    `${projectPath(projectId)}/edits/${encodeURIComponent(filename)}`,
    {
      method: "PUT",
      body: JSON.stringify({ document }),
    },
  );
}

export function renameEdit(
  projectId: string,
  filename: string,
  newFilename: string,
) {
  return api<{ filename: string }>(
    `${projectPath(projectId)}/edits/${encodeURIComponent(filename)}/rename`,
    {
      method: "POST",
      body: JSON.stringify({ filename: newFilename }),
    },
  );
}

export function deleteEdit(projectId: string, filename: string) {
  return api<void>(
    `${projectPath(projectId)}/edits/${encodeURIComponent(filename)}`,
    {
      method: "DELETE",
    },
  );
}

export function getMediaUrl(projectId: string, mediaPath: string) {
  const encodedPath = mediaPath.split("/").map(encodeURIComponent).join("/");
  return `${projectPath(projectId)}/media/${encodedPath}`;
}

export interface ImportFile {
  source_relative_path: string;
  filename: string;
  size_bytes: number;
  status: "new" | "already_imported" | "conflict";
}

export interface ImportPlan {
  source: string;
  total_source_files: number;
  already_imported: number;
  new_files: number;
  conflicts: number;
  files: ImportFile[];
}

export interface ImportResult {
  imported: number;
  skipped: number;
  conflicts: number;
  errors: string[];
  everything_up_to_date?: boolean;
}

export interface DetectedImportSource {
  path: string;
  label: string;
  source_type: "gopro" | "gopro_usb";
  reason: string;
}

export function getDetectedImportSources(signal?: AbortSignal) {
  return api<DetectedImportSource[]>("/api/import-sources", { signal });
}

export function scanGoProImport(projectId: string, sourcePath: string) {
  return api<ImportPlan>(`${projectPath(projectId)}/imports/scan`, {
    method: "POST",
    body: JSON.stringify({ source_path: sourcePath }),
  });
}

export function importGoProFiles(
  projectId: string,
  sourcePath: string,
  selectedPaths: string[],
) {
  return api<MediaJob>(`${projectPath(projectId)}/imports`, {
    method: "POST",
    body: JSON.stringify({
      source_path: sourcePath,
      selected_paths: selectedPaths,
    }),
  });
}

export function getExportUrl(
  projectId: string,
  filename: string,
  social = false,
) {
  const collection = social ? "social-exports" : "exports";
  return `${projectPath(projectId)}/${collection}/${encodeURIComponent(filename)}`;
}

export function deleteExportFile(
  projectId: string,
  filename: string,
  social = false,
) {
  const collection = social ? "social-exports" : "exports";
  return api<void>(
    `${projectPath(projectId)}/${collection}/${encodeURIComponent(filename)}`,
    {
      method: "DELETE",
    },
  );
}

export function getProjectExports(projectId: string, signal?: AbortSignal) {
  return api<ProjectExports>(`${projectPath(projectId)}/exports`, { signal });
}

export function getSocialOptions(projectId: string, signal?: AbortSignal) {
  return api<SocialOptions>(`${projectPath(projectId)}/social-options`, {
    signal,
  });
}

export function startRender(
  projectId: string,
  editFilename: string,
  mode: "accurate" | "fast",
) {
  return api<MediaJob>(`${projectPath(projectId)}/renders`, {
    method: "POST",
    body: JSON.stringify({ edit_filename: editFilename, mode }),
  });
}

export function startSocialExport(
  projectId: string,
  sourceFilename: string,
  preset: string,
  framing: "crop" | "fit",
) {
  return api<MediaJob>(`${projectPath(projectId)}/social-exports`, {
    method: "POST",
    body: JSON.stringify({ source_filename: sourceFilename, preset, framing }),
  });
}

export function startProbe(projectId: string, force = false) {
  return api<MediaJob>(`${projectPath(projectId)}/probe`, {
    method: "POST",
    body: JSON.stringify({ force }),
  });
}

export function startThumbnails(projectId: string, force = false) {
  return api<MediaJob>(`${projectPath(projectId)}/thumbnails`, {
    method: "POST",
    body: JSON.stringify({ force }),
  });
}

export function getMediaJob(projectId: string, jobId: string) {
  return api<MediaJob>(
    `${projectPath(projectId)}/jobs/${encodeURIComponent(jobId)}`,
  );
}

export function getJournalEntries(projectId: string, signal?: AbortSignal) {
  return api<JournalEntry[]>(`${projectPath(projectId)}/journal`, { signal });
}

export function createJournalEntry(
  projectId: string,
  payload: JournalEntryPayload,
) {
  return api<JournalEntry>(`${projectPath(projectId)}/journal`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateJournalEntry(
  projectId: string,
  entryId: string,
  payload: JournalEntryPayload,
) {
  return api<JournalEntry>(
    `${projectPath(projectId)}/journal/${encodeURIComponent(entryId)}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
}

export function deleteJournalEntry(projectId: string, entryId: string) {
  return api<void>(
    `${projectPath(projectId)}/journal/${encodeURIComponent(entryId)}`,
    {
      method: "DELETE",
    },
  );
}
