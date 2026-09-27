# Amris Video Tools — Copilot Instructions

## Project Purpose

Amris Video Tools is a personal, local-first video management and editing application primarily designed for working with GoPro footage.

The project originally started as a Python CLI application. It is now being expanded with a React web interface backed by FastAPI.

The long-term architecture is:

```text
React
  ↓
FastAPI HTTP API
  ↓
Python service/domain layer
  ↓
ffmpeg / ffprobe / filesystem / project files
```

The React application should eventually provide the primary interactive user experience, while Python remains responsible for filesystem access, project management, media processing, rendering, and other backend operations.

This is a local application. FastAPI and React normally run on the same machine as the user's video files.

---

## Important: Preserve the Existing CLI

The repository contains an existing Python CLI implementation with working video-management and rendering functionality.

Treat this code as existing/legacy functionality that must remain working during the React migration.

Do not:

- Rewrite existing CLI commands unless explicitly requested.
- Remove existing CLI functionality because equivalent React functionality is being added.
- Change existing project formats without an explicit migration decision.
- Perform unrelated refactors of legacy Python code while implementing React/FastAPI features.
- Make the FastAPI layer invoke CLI commands as subprocesses or simulate CLI usage.

Prefer leaving existing CLI code untouched unless a task specifically requires modifying it.

When existing functionality needs to be shared between the CLI and FastAPI, extract or reuse the underlying Python functionality carefully rather than making one interface depend on the other.

The desired direction is:

```text
             ┌── CLI
             │
service/domain layer
             │
             └── FastAPI
```

Not:

```text
FastAPI → CLI
```

and not:

```text
CLI → FastAPI
```

Both should eventually be thin interfaces over reusable Python functionality.

---

## Migration Strategy

The React/FastAPI migration is incremental.

Do not attempt to rewrite the entire application at once.

When implementing a feature:

1. Understand the existing Python implementation first.
2. Identify the underlying behavior that should be preserved.
3. Add or reuse a Python service/domain function where appropriate.
4. Expose the required functionality through a small FastAPI endpoint.
5. Consume that endpoint from React.
6. Preserve existing CLI behavior.

Prefer small vertical slices that work end-to-end.

For example:

```text
React Clips page
    ↓
GET /api/projects/{project_id}/clips
    ↓
FastAPI clips router
    ↓
Python clip/project service
    ↓
project filesystem
```

Avoid large speculative abstractions before they are needed.

---

## React Application

The React source lives under:

```text
frontend/
```

The frontend uses:

- React
- TypeScript
- Vite
- Chakra UI v2
- React Router
- react-icons / Lucide icons

The frontend is a client of the FastAPI API.

React should not attempt to directly understand or manipulate the user's filesystem.

Use relative API URLs:

```ts
fetch("/api/projects");
```

Do not hard-code development backend URLs such as:

```ts
fetch("http://127.0.0.1:8765/api/projects");
```

Vite proxies API requests during development. In the packaged/local application, FastAPI will eventually serve the built frontend.

Reusable HTTP calls belong under:

```text
frontend/src/api/
```

rather than being scattered throughout page components.

---

## Frontend State and Layout

Global application configuration is managed separately from project state.

Current concepts include:

```text
AppConfigContext
    global application configuration

ProjectContext
    discovered Video Tools projects
```

Avoid introducing additional state-management libraries unless complexity clearly requires them.

The routing/layout model is:

```text
AppBootstrap
│
├── /setup
│
└── AppLayout
    ├── TopBar
    ├── /
    ├── /settings
    │
    └── /projects/:projectId
        └── ProjectLayout
            ├── Sidebar
            └── project-specific pages
```

`TopBar` is global.

`Sidebar` is project-specific and must only appear when a project is selected.

Global functionality such as Projects and Settings belongs in the global application layout.

Project functionality such as Overview, Clips, Import, Editor, Renders, Social Export, and Journal belongs in the project layout.

---

## FastAPI

FastAPI code lives under:

```text
src/videotools/web/
```

FastAPI should primarily act as an HTTP adapter.

Keep routers relatively thin.

Avoid putting substantial filesystem scanning, ffmpeg logic, rendering logic, or project-domain logic directly into route handlers.

Preferred structure:

```text
router
  ↓
Python service/domain function
  ↓
filesystem / ffmpeg / existing project functionality
```

Pydantic request/response models should clearly describe the API contract.

Do not expose internal implementation details to React unless the frontend actually needs them.

---

## Video Tools Projects

Video projects are filesystem-backed.

A project is identified by a `project.toml` file in its root directory.

Example:

```toml
name = "portugal-2026"
timezone = "Europe/Copenhagen"

[paths]
clips = "clips"
metadata = "metadata"
exports = "exports"
journal = "journal.json"

[resolve]
project_name = "portugal-2026"
```

Do not introduce a new project marker such as `video-project.json`.

Existing project configuration and directory conventions should remain compatible.

Configured paths must be respected rather than assuming directory names everywhere.

For example, prefer the configured `paths.clips` value over blindly assuming that every project uses a directory named `clips`.

Treat `[resolve]` as an internal project-resolution concern unless a feature specifically requires exposing it.

---

## Global Application Configuration

Global Video Tools configuration is different from project configuration.

It contains settings applying to the application as a whole, such as the directory containing Video Tools projects.

Global configuration is stored in the operating system's appropriate user configuration location using Python `platformdirs`.

It does not belong inside the source repository or an individual video project.

React accesses and modifies global configuration through FastAPI.

---

## Media and Filesystem Responsibilities

Python owns filesystem and media access.

React should receive structured API data and media URLs from FastAPI.

Do not send arbitrary absolute filesystem paths from React and expect the browser to access them directly.

Media serving must support browser seeking where required. Existing media-serving behavior may include HTTP Range support and should not be casually replaced with a simpler implementation that breaks seeking.

Video processing should continue to use the existing ffmpeg/ffprobe-based Python functionality where possible.

---

## Rendering

Rendering is an expensive backend operation and belongs in Python.

Existing rendering behavior includes different rendering modes and project-specific output handling.

Do not reimplement video rendering in React.

The frontend should eventually initiate rendering and display its status/results through backend APIs.

Preserve existing render behavior unless a task explicitly changes it.

---

## General Development Principles

Prefer:

- Incremental migration.
- Small focused changes.
- Existing project compatibility.
- Reusing proven Python behavior.
- Thin API routers.
- Typed API contracts.
- Simple React components.
- Clear separation between global and project-specific functionality.
- Platform-agnostic Python code where practical.
- `pathlib.Path` for filesystem paths.

Avoid:

- Unrequested rewrites.
- Duplicating existing Python functionality in FastAPI.
- Making React aware of Python implementation details.
- Hard-coded project names or filesystem locations.
- Hard-coded development server URLs.
- Introducing new dependencies without a clear benefit.
- Premature abstraction.
- Changing existing file formats casually.
- Large refactors mixed into feature work.

When uncertain about existing behavior, inspect the existing implementation before replacing or modifying it.

---

## Current Migration Priority

The immediate goal is not to eliminate the CLI.

The goal is to progressively build a polished React interface over the existing Video Tools capabilities while establishing a reusable Python service layer underneath both interfaces.

Existing CLI functionality should continue working throughout this process.

A feature should generally be considered successfully migrated when:

```text
React UI
    ↓
FastAPI API
    ↓
shared Python functionality
    ↓
existing Video Tools project/media behavior
```

works end-to-end without requiring the old browser UI and without breaking the CLI.

## Cross-Platform Support

Amris Video Tools is actively developed and used on both Windows and Linux, with Arch Linux being a primary Linux environment.

All new Python, FastAPI, CLI, lifecycle, filesystem, and process-management functionality should work on both platforms.

Prefer cross-platform Python facilities such as `pathlib.Path`, `shutil.which()`, `sys.executable`, `platformdirs`, and `subprocess`. Do not hard-code Windows or Unix filesystem paths, executable locations, path separators, or shell-specific commands.

Avoid `shell=True` unless there is a specific, documented platform requirement. If platform-specific behavior is genuinely necessary, keep it isolated and explicitly guarded rather than making the general implementation platform-specific.
