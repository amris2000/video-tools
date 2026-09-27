import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { getProjects, type Project } from "../api/projects";
import { useAppConfig } from "./AppConfigContext";

interface ProjectContextValue {
  projects: Project[];
  loading: boolean;
  error: string | null;
  refreshProjects: () => Promise<void>;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);
  const { config, loading: configLoading } = useAppConfig();
  async function refreshProjects() {
    setLoading(true);
    setError(null);

    try {
      const discoveredProjects = await getProjects();

      setProjects(discoveredProjects);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load projects.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (configLoading) {
      return;
    }

    if (!config?.configured) {
      setProjects([]);
      setLoading(false);
      return;
    }

    void refreshProjects();
  }, [config?.configured, configLoading]);

  return (
    <ProjectContext.Provider
      value={{
        projects,
        loading,
        error,
        refreshProjects,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProjects() {
  const context = useContext(ProjectContext);

  if (!context) {
    throw new Error("useProjects must be used inside ProjectProvider.");
  }

  return context;
}
