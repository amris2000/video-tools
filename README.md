# Amris Video Tools

Amris Video Tools is a local-first video management and editing application primarily built for working with GoPro footage.

The project combines a React frontend with a Python/FastAPI backend and existing CLI-based video processing tools.

The application is designed to keep source code separate from video projects and their media.

## Architecture

```text
React
  ↓
FastAPI
  ↓
Python services
  ↓
ffmpeg / ffprobe / filesystem
```

Python remains responsible for filesystem access, project management, metadata, thumbnails, rendering, and other media-processing tasks.

The React application provides the primary interactive user interface.

Existing CLI functionality is being migrated incrementally and remains available.

## Repository Structure

```text
video-tools/
├── frontend/               # React/Vite source
├── src/
│   └── videotools/
│       ├── web/            # FastAPI application
│       ├── services/       # Shared application/domain services
│       ├── cli.py          # CLI entry point
│       └── ...             # Existing video tooling
├── docs/
├── tests/
├── build/
│   └── frontend/           # Generated production frontend
└── pyproject.toml
```

The generated `build/frontend/` directory is not committed to Git.

## Video Projects

Video projects live outside the source repository.

A typical project looks like:

```text
portugal-2026/
├── project.toml
├── clips/
├── edits/
├── metadata/
├── exports/
├── exports-social/
└── journal.json
```

A project is identified by its `project.toml`.

Project paths are configurable and should remain relative to the project root where possible.

Example:

```toml
name = "portugal-2026"
timezone = "Europe/Copenhagen"

[paths]
clips = "clips"
metadata = "metadata"
edits = "edits"
exports = "exports"
exports_social = "exports-social"
journal = "journal.json"
```

Large media files and generated project data are therefore kept outside the Git repository.

## Installation

See:

```text
docs/INSTALL.md
```

for the complete first-time installation, development, update, Windows, and Linux instructions.

## Normal Use

Activate the Python virtual environment and run:

```text
video-tools
```

This starts FastAPI, serves the production React frontend, and opens the application in the default browser.

The application normally runs at:

```text
http://127.0.0.1:8765
```

Stop it with `Ctrl+C`.

## Development

Activate the virtual environment and run:

```text
video-tools dev
```

This starts:

```text
FastAPI     http://127.0.0.1:8765
React/Vite  http://localhost:5173
```

Use the Vite address while developing the frontend.

## Updating

After pulling new source code:

```text
git pull
python -m pip install -e .
video-tools update
```

Then start the application normally:

```text
video-tools
```

## Main Lifecycle Commands

| Command               | Purpose                                                           |
| --------------------- | ----------------------------------------------------------------- |
| `video-tools`         | Run the normal application                                        |
| `video-tools dev`     | Run FastAPI + Vite development servers                            |
| `video-tools install` | Install frontend dependencies and create the production build     |
| `video-tools update`  | Refresh frontend dependencies and rebuild the production frontend |
| `video-tools help`    | Show available commands                                           |

Existing project-specific CLI commands remain available during the React migration.

## Current React Migration

Video Tools originally began as a Python CLI and local browser-based editor.

Functionality is being moved incrementally toward:

```text
React UI
    ↓
FastAPI API
    ↓
shared Python services
    ↓
existing project/media functionality
```

The existing CLI is intentionally preserved during this process.

The current React application includes:

- application setup and configuration
- project discovery
- project overview and statistics
- clip browsing
- reusable clip viewing/selection components
- version-1 edit timeline management
- project-scoped rendering and export playback
- social conversion of completed renders

Import and Journal remain deferred. Existing Journal CLI functionality and the standalone `video-tools editor`, `video-tools render`, and `video-tools social` commands remain available.

## Development Principles

The project favors:

- local-first operation
- filesystem-backed projects
- reusable Python services
- thin FastAPI endpoints
- simple React components
- incremental migration
- preserving existing CLI functionality
- cross-platform Windows and Linux support
- FFmpeg/FFprobe for media processing

React should not directly manipulate the filesystem.

FastAPI and the CLI should share underlying Python functionality rather than calling each other.

## Platform Support

Video Tools is developed for both:

- Windows
- Linux, with Arch Linux as a primary Linux environment

Platform-neutral Python facilities such as `pathlib`, `subprocess`, `shutil.which`, and `platformdirs` should be preferred.

## More Documentation

See the `docs/` directory for additional documentation.

In particular:

```text
docs/INSTALL.md
```

contains the practical installation and everyday usage guide.
