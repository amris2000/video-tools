import { api } from "./client";

export interface ProjectPaths {
  clips: string;
  metadata: string;
  exports: string;
  journal: string;
}

export interface Project {
  id: string;
  name: string;
  path: string;
  timezone: string | null;
  paths: ProjectPaths;
}

export function getProjects(): Promise<Project[]> {
  return api<Project[]>("/api/projects");
}
