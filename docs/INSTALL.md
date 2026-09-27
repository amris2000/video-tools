# Amris Video Tools --- Installation and Usage

Amris Video Tools is a local application for managing and editing video
projects.

The application consists of:

- a Python/FastAPI backend
- a React frontend
- FFmpeg/FFprobe for video processing

The normal application does not require the React development server to
be running. The React frontend is built ahead of time and served
directly by FastAPI.

## Requirements

Install the following system dependencies:

- Git
- Python
- FFmpeg and FFprobe
- Node.js and npm

Node.js/npm are required for installing, updating, and developing the
application. They are not required while simply running an already-built
installation.

Verify the tools with:

```text
python --version
ffmpeg -version
ffprobe -version
node --version
npm --version
```

---

# First-Time Installation

Clone the repository:

```text
git clone <repository-url>
cd video-tools
```

Create a Python virtual environment.

## Windows PowerShell

```text
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## Linux

```text
python -m venv .venv
source .venv/bin/activate
```

Upgrade pip and install Video Tools in editable mode:

```text
python -m pip install --upgrade pip
python -m pip install -e .
```

Then install/build the application:

```text
video-tools install
```

This command:

1.  checks that FFmpeg, FFprobe, Node.js, and npm are available
2.  installs the React frontend dependencies
3.  builds the production React frontend
4.  verifies that the frontend build was created successfully

After this completes, Video Tools is ready to run.

---

# Normal Use

After restarting the computer, open a terminal and navigate to the Video
Tools repository.

## Windows PowerShell

```text
cd C:\Users\Frederik\Projects\video-tools
.\.venv\Scripts\Activate.ps1
video-tools
```

## Linux

```text
cd ~/Projects/video-tools
source .venv/bin/activate
video-tools
```

`video-tools` starts the local FastAPI server and opens the application
in the default browser.

The application runs locally at:

```text
http://127.0.0.1:8765
```

Stop the application with:

```text
Ctrl+C
```

You do not need to run npm, Vite, or `video-tools install` every time
the computer starts.

---

# Development

Use development mode when changing the React frontend or FastAPI
backend.

Activate the virtual environment and run:

```text
video-tools dev
```

Development mode starts:

```text
FastAPI    http://127.0.0.1:8765
React/Vite http://localhost:5173
```

Open the Vite address while developing:

```text
http://localhost:5173
```

Vite proxies API and media requests to FastAPI.

Changes to the frontend are handled by the Vite development server,
while FastAPI runs with automatic reload enabled.

Stop both development servers with:

```text
Ctrl+C
```

Do not use `video-tools dev` for normal everyday use.

---

# Updating Video Tools

After pulling new source code:

```text
git pull
```

Activate the virtual environment if necessary.

Then refresh the Python editable installation:

```text
python -m pip install -e .
```

Finally run:

```text
video-tools update
```

`video-tools update` refreshes frontend dependencies and rebuilds the
production React frontend.

The normal update workflow is therefore:

```text
git pull
python -m pip install -e .
video-tools update
video-tools
```

`video-tools update` does not perform `git pull` itself.

---

# Command Overview

- `video-tools` --- starts the normal production application.
- `video-tools dev` --- starts FastAPI and the React/Vite development
  server.
- `video-tools install` --- performs the initial frontend dependency
  installation and production build.
- `video-tools update` --- refreshes frontend dependencies and
  rebuilds the production frontend.
- `video-tools help` --- lists all available Video Tools commands.

Existing project-specific commands such as `render`, `social`, `probe`,
and `journal` continue to operate from within a video project.

---

# Production vs Development

Normal use:

```text
video-tools
       |
       v
    FastAPI
       |
       +-- /api/*
       |
       +-- built React frontend
                 |
                 v
        http://127.0.0.1:8765
```

Development:

```text
video-tools dev
       |
       +-- FastAPI
       |      +-- http://127.0.0.1:8765
       |
       +-- Vite / React
              +-- http://localhost:5173
```

The production React build is stored in:

```text
build/frontend/
```

This directory is generated and is not committed to Git.

The React source code lives in:

```text
frontend/
```

---

# Quick Reference

## I just restarted my computer

### Windows

```text
cd C:\Users\Frederik\Projects\video-tools
.\.venv\Scripts\Activate.ps1
video-tools
```

### Linux

```text
cd ~/Projects/video-tools
source .venv/bin/activate
video-tools
```

## I want to work on the application

Activate the virtual environment, then:

```text
video-tools dev
```

## I pulled new code

```text
git pull
python -m pip install -e .
video-tools update
video-tools
```

## I changed only React code while using dev mode

Keep using:

```text
video-tools dev
```

Vite handles the development frontend.

Before using normal production mode again, rebuild it:

```text
video-tools update
```

## I changed only Python code

Editable installation means most Python source changes are immediately
available.

Restart:

```text
video-tools
```

or, during development:

```text
video-tools dev
```

If dependencies or packaging configuration changed, run:

```text
python -m pip install -e .
```
