import { api } from "./client";

export interface AppConfig {
  configured: boolean;
  projects_directory: string | null;
}

export interface ConfigUpdate {
  projects_directory: string;
}

export function getConfig(): Promise<AppConfig> {
  return api<AppConfig>("/api/config");
}

export function updateConfig(update: ConfigUpdate): Promise<AppConfig> {
  return api<AppConfig>("/api/config", {
    method: "PUT",
    body: JSON.stringify(update),
  });
}
