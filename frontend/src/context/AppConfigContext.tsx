import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { getConfig, type AppConfig } from "../api/config";

interface AppConfigContextValue {
  config: AppConfig | null;
  loading: boolean;
  error: string | null;
  setConfig: (config: AppConfig) => void;
}

const AppConfigContext = createContext<AppConfigContextValue | null>(null);

interface AppConfigProviderProps {
  children: ReactNode;
}

export function AppConfigProvider({ children }: AppConfigProviderProps) {
  const [config, setConfig] = useState<AppConfig | null>(null);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const loadedConfig = await getConfig();
        setConfig(loadedConfig);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Could not load Video Tools configuration.",
        );
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, []);

  return (
    <AppConfigContext.Provider
      value={{
        config,
        loading,
        error,
        setConfig,
      }}
    >
      {children}
    </AppConfigContext.Provider>
  );
}

export function useAppConfig() {
  const context = useContext(AppConfigContext);

  if (!context) {
    throw new Error("useAppConfig must be used inside AppConfigProvider.");
  }

  return context;
}
