# Installing Amris Video Tools

This guide explains how to set up Amris Video Tools on a new machine after cloning the repository.

Video Tools consists of two main parts:

- A Python backend and CLI
- A React frontend built with Vite

Python handles project management, filesystem access, video processing, ffmpeg/ffprobe integration, and the FastAPI backend.

React provides the graphical user interface.

---

# 1. Prerequisites

Install the following software before setting up Video Tools.

## Git

Verify:

```bash
git --version
```

## Python

Video Tools requires a modern Python installation.

Verify:

```bash
python --version
```

The project is currently developed using Python 3.13.

## Node.js and npm

Node.js is required to build the React frontend.

Verify:

```bash
node --version
npm --version
```

Use a current Node.js LTS release.

## FFmpeg

Video Tools uses FFmpeg and FFprobe for video inspection and rendering.

Verify both commands are available:

```bash
ffmpeg -version
ffprobe -version
```

They must be available on the system `PATH`.

---

# 2. Clone the repository

Clone the repository from GitHub:

```bash
git clone <repository-url>
cd video-tools
```

For example, if the repository is named `video-tools`, the repository root should contain files/directories similar to:

```text
video-tools/
├── docs/
├── frontend/
├── src/
├── tests/
├── pyproject.toml
└── ...
```

All commands below assume the current directory is the repository root unless otherwise stated.

---

# 3. Create the Python virtual environment

Create a virtual environment inside the repository:

```bash
python -m venv .venv
```

## Windows PowerShell

Activate it with:

```powershell
.\.venv\Scripts\Activate.ps1
```

The terminal should now show something similar to:

```text
(.venv) PS C:\...\video-tools>
```

## Linux / macOS

Activate it with:

```bash
source .venv/bin/activate
```

Verify that the correct Python interpreter is active:

```bash
python -c "import sys; print(sys.executable)"
```

The path should point inside the repository's `.venv`.

---

# 4. Install the Python project

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

Install Video Tools in editable mode:

```bash
python -m pip install -e .
```

Editable mode means changes made under `src/videotools/` are immediately reflected without reinstalling the package.

Verify the installation:

```bash
python -c "import videotools; print(videotools.__file__)"
```

The path should point into:

```text
video-tools/src/videotools/
```

The Video Tools CLI should also be available.

For example:

```bash
video-tools help
```

---

# 5. Install the React frontend dependencies

Move into the frontend directory:

```bash
cd frontend
```

Install the JavaScript dependencies:

```bash
npm install
```

This creates:

```text
frontend/node_modules/
```

`node_modules` is generated locally and is not committed to Git.

Return to the repository root when finished:

```bash
cd ..
```

---

# 6. Build the React frontend

From the frontend directory:

```bash
cd frontend
npm run build
```

The compiled frontend is written to:

```text
build/frontend/
```

relative to the repository root.

Return to the repository root:

```bash
cd ..
```

The generated frontend build is not committed to Git and must therefore be built after cloning the repository.

---

# 7. Verify FastAPI

Start the backend from the repository root:

```bash
python -m uvicorn videotools.web.app:app --reload --port 8765
```

The API should be available at:

```text
http://127.0.0.1:8765
```

FastAPI's development documentation is available at:

```text
http://127.0.0.1:8765/docs
```

The health endpoint should respond successfully:

```text
http://127.0.0.1:8765/api/health
```

Expected response:

```json
{
  "status": "ok"
}
```

Press `Ctrl+C` to stop the server.

---

# 8. Run the React frontend in development mode

During frontend development, React and FastAPI run as two separate development servers.

Open one terminal in the repository root, activate the Python virtual environment, and start FastAPI:

```bash
python -m uvicorn videotools.web.app:app --reload --port 8765
```

Open a second terminal:

```bash
cd frontend
npm run dev
```

Vite normally starts the frontend at:

```text
http://localhost:5173
```

Open this address in a browser.

The Vite development server proxies backend requests such as:

```text
/api/...
```

to the FastAPI server running on port `8765`.

React code should therefore use relative API URLs such as:

```text
/api/projects
```

rather than hard-coded FastAPI addresses.

---

# 9. First-time Video Tools configuration

When the React application is opened for the first time, Video Tools asks for the directory containing Video Tools projects.

For example, on Windows:

```text
C:\Users\<username>\Videos\Projects
```

On Linux:

```text
/home/<username>/Videos/Projects
```

This is the parent directory containing individual projects.

For example:

```text
Projects/
├── portugal-2026/
│   ├── project.toml
│   ├── clips/
│   ├── metadata/
│   └── ...
│
└── another-project/
    ├── project.toml
    └── ...
```

A Video Tools project is identified by a `project.toml` file in its root directory.

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

The global projects-directory setting is stored outside the Git repository in the operating system's normal user configuration location.

It is therefore normal to configure this again when installing Video Tools on a new machine.

---

# 10. Normal development startup

After the initial installation, day-to-day development only requires activating the Python environment and starting the two development servers.

## Terminal 1 — backend

From the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn videotools.web.app:app --reload --port 8765
```

On Linux/macOS:

```bash
source .venv/bin/activate
python -m uvicorn videotools.web.app:app --reload --port 8765
```

## Terminal 2 — frontend

```bash
cd frontend
npm run dev
```

Then open:

```text
http://localhost:5173
```

---

# 11. Updating an existing installation

After pulling changes from Git:

```bash
git pull
```

If Python dependencies may have changed, activate the virtual environment and run:

```bash
python -m pip install -e .
```

If frontend dependencies may have changed:

```bash
cd frontend
npm install
cd ..
```

If the production frontend build is needed, rebuild it:

```bash
cd frontend
npm run build
cd ..
```

There is no need to recreate `.venv` or reinstall everything after every Git pull.

---

# 12. Troubleshooting

## `ModuleNotFoundError: No module named 'videotools'`

Make sure the virtual environment is activated:

```powershell
.\.venv\Scripts\Activate.ps1
``
```
