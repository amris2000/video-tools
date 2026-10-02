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
  journal: {
    date: string | null;
    activity: string | null;
    location: string | null;
    start_time: string | null;
    end_time: string | null;
    tags: string[];
    highlight: string | null;
  } | null;
  gps: {
    available: boolean;
    latitude: number | null;
    longitude: number | null;
    altitude: number | null;
    speed: number | null;
    datetime: string | null;
  } | null;
}

export function getClips(projectId: string, signal?: AbortSignal) {
  return api<Clip[]>(
    "/api/projects/" + encodeURIComponent(projectId) + "/clips",
    { signal },
  );
}
