import { Navigate, Route, Routes } from "react-router-dom";

import { AppBootstrap } from "./components/AppBootstrap";
import { AppLayout } from "./components/layout/AppLayout";
import { ProjectLayout } from "./components/layout/ProjectLayout";

import { ClipBrowserDemo } from "./examples/ClipBrowserDemo";
import { ClipsPage } from "./pages/ClipsPage";
import { EditorPage } from "./pages/EditorPage";
import { ExportsPage } from "./pages/ExportsPage";
import { HomePage } from "./pages/HomePage";
import { OverviewPage } from "./pages/OverviewPage";
import { RenderPage } from "./pages/RenderPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SetupPage } from "./pages/SetupPage";

function App() {
  return (
    <Routes>
      <Route element={<AppBootstrap />}>
        {/*
          Setup deliberately sits outside AppLayout.
          First-time setup doesn't need the normal app shell.
        */}
        <Route path="/setup" element={<SetupPage />} />

        {/*
          Normal application shell.
          Everything here gets the global TopBar.
        */}
        <Route element={<AppLayout />}>
          <Route path="/" element={<HomePage />} />

          <Route path="/settings" element={<SettingsPage />} />

          {/*
            Project-specific shell.
            Everything here additionally gets the Sidebar.
          */}
          <Route path="/projects/:projectId" element={<ProjectLayout />}>
            <Route index element={<OverviewPage />} />
            <Route path="clips" element={<ClipsPage />} />
            <Route path="editor" element={<EditorPage />} />
            <Route path="render" element={<RenderPage />} />
            <Route path="exports" element={<ExportsPage />} />
            {import.meta.env.DEV && <Route path="clips/demo" element={<ClipBrowserDemo />} />}
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
