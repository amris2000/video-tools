import { api } from "./client";

export interface Clip {
  /** Project-relative identity, scoped to projectId. */
  path: string;
  /** Path relative to the configured project clips directory, for media URLs. */
  media_path: string;
  name: string;
  duration: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  creation_time: string | null;
  thumbnail_url: string | null;
}

export function getClips(projectId: string, signal?: AbortSignal) {
  return api<Clip[]>("/api/projects/" + encodeURIComponent(projectId) + "/clips", { signal });
}
