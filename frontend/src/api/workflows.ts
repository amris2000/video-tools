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
  kind: "render" | "social_export";
  status: "queued" | "running" | "completed" | "failed";
  output_filename: string | null;
  error: string | null;
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

const projectPath = (projectId: string) =>
  `/api/projects/${encodeURIComponent(projectId)}`;

export function getEdits(projectId: string, signal?: AbortSignal) {
  return api<EditSummary[]>(`${projectPath(projectId)}/edits`, { signal });
}

export function getEdit(projectId: string, filename: string) {
  return api<EditDocument>(`${projectPath(projectId)}/edits/${encodeURIComponent(filename)}`);
}

export function createEdit(projectId: string, filename?: string) {
  return api<EditResponse>(`${projectPath(projectId)}/edits`, {
    method: "POST",
    body: JSON.stringify({ filename }),
  });
}

export function saveEdit(projectId: string, filename: string, document: EditDocument) {
  return api<EditResponse>(`${projectPath(projectId)}/edits/${encodeURIComponent(filename)}`, {
    method: "PUT",
    body: JSON.stringify({ document }),
  });
}

export function renameEdit(projectId: string, filename: string, newFilename: string) {
  return api<{ filename: string }>(`${projectPath(projectId)}/edits/${encodeURIComponent(filename)}/rename`, {
    method: "POST",
    body: JSON.stringify({ filename: newFilename }),
  });
}

export function deleteEdit(projectId: string, filename: string) {
  return api<void>(`${projectPath(projectId)}/edits/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });
}

export function getMediaUrl(projectId: string, relativePath: string) {
  const encodedPath = relativePath.split("/").map(encodeURIComponent).join("/");
  return `${projectPath(projectId)}/media/${encodedPath}`;
}

export function getExportUrl(projectId: string, filename: string, social = false) {
  const collection = social ? "social-exports" : "exports";
  return `${projectPath(projectId)}/${collection}/${encodeURIComponent(filename)}`;
}

export function getProjectExports(projectId: string, signal?: AbortSignal) {
  return api<ProjectExports>(`${projectPath(projectId)}/exports`, { signal });
}

export function getSocialOptions(projectId: string, signal?: AbortSignal) {
  return api<SocialOptions>(`${projectPath(projectId)}/social-options`, { signal });
}

export function startRender(projectId: string, editFilename: string, mode: "accurate" | "fast") {
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

export function getMediaJob(projectId: string, jobId: string) {
  return api<MediaJob>(`${projectPath(projectId)}/jobs/${encodeURIComponent(jobId)}`);
}
