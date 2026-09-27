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

export function getProjects(): Promise<Project[]> {
  return api<Project[]>("/api/projects");
}

export function getProject(projectId: string): Promise<ProjectDetails> {
  return api<ProjectDetails>(`/api/projects/${encodeURIComponent(projectId)}`);
}
