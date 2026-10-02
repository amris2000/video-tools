import { api } from "./client";

export interface ProjectPaths {
  clips: string;
  metadata: string;
  edits: string;
  exports: string;
  exports_social: string;
  journal: string;
}

export interface Project {
  id: string;
  name: string;
  path: string;
  timezone: string | null;
  paths: ProjectPaths;
}

export interface ProjectStats {
  clips: number;
  edits: number;
  renders: number;
  social_exports: number;
}

export interface ProjectDetails extends Project {
  stats: ProjectStats;
}

export interface ProjectCreateRequest {
  name: string;
}

export function getProjects(): Promise<Project[]> {
  return api<Project[]>("/api/projects");
}

export function createProject(request: ProjectCreateRequest): Promise<Project> {
  return api<Project>("/api/projects", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function deleteProject(projectId: string): Promise<void> {
  return api<void>(`/api/projects/${encodeURIComponent(projectId)}`, {
    method: "DELETE",
  });
}

export function getProject(
  projectId: string,
  signal?: AbortSignal,
): Promise<ProjectDetails> {
  return api<ProjectDetails>(`/api/projects/${encodeURIComponent(projectId)}`, {
    signal,
  });
}
