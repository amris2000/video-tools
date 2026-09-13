# video-tools

Personal Python tooling for organizing, analyzing, and preparing video footage for editing in DaVinci Resolve.

The main design principle is to keep **code** separate from **video projects and media**.

```text
C:\Users\Frederik\
│
├── Projects\                         # CODE
│   └── video-tools\                  # This Git repository
│       ├── .git\
│       ├── .venv\
│       ├── pyproject.toml
│       ├── README.md
│       ├── src\
│       │   └── videotools\
│       │       ├── __init__.py
│       │       ├── cli.py
│       │       ├── project.py
│       │       ├── metadata.py
│       │       ├── journal.py
│       │       ├── ingest.py
│       │       └── resolve.py
│       └── tests\
│
└── Videos\
    └── Projects\                     # VIDEO PROJECTS / DATA
        ├── vacation-2026\
        │   ├── project.toml
        │   ├── clips\
        │   ├── edits\
        │   ├── metadata\
        │   ├── exports\
        │   └── journal.json
        │
        ├── scripting-test\
        │   ├── project.toml
        │   ├── clips\
        │   ├── edits\
        │   ├── metadata\
        │   └── exports\
        │
        └── another-video\
```

---

## Philosophy

`video-tools` contains reusable Python code.

Individual video projects contain footage, metadata, journals, generated reports, and exports.

In other words:

```text
video-tools
    = HOW to process video projects

project.toml
    = HOW a particular project is configured

Video project directory
    = WHAT the tools operate on
```

Large video files are therefore kept outside the Git repository.

---

## Code Repository

The Python project lives at:

```text
C:\Users\Frederik\Projects\video-tools
```

The package itself lives under:

```text
src\videotools\
```

The modules have roughly the following responsibilities:

### `cli.py`

Command-line interface.

Eventually this should provide commands such as:

```text
video-tools init
video-tools ingest
video-tools probe
video-tools journal
video-tools report
```

### `project.py`

Project discovery and configuration.

Responsible for finding and loading `project.toml`.

### `metadata.py`

Video metadata extraction.

This can use tools such as `ffprobe` to extract:

- duration
- resolution
- frame rate
- video codec
- pixel format
- audio codec
- sample rate
- timestamps

### `journal.py`

Vacation/shoot journal functionality.

Journal entries can record:

- date
- start/end time
- location
- activity
- tags
- highlights
- notes

This information can later be matched against camera timestamps.

### `ingest.py`

Responsible for copying and organizing footage from SD cards or other sources.

Eventually this should also handle:

- copy verification
- duplicate detection
- metadata extraction
- folder creation
- backup verification

### `resolve.py`

DaVinci Resolve integration.

Resolve Free does not expose the same external scripting connection as Resolve Studio, so Resolve automation is run internally through:

```text
Workspace > Scripts
```

Internal Resolve scripts can obtain the Resolve object using:

```python
resolve = app.GetResolve()
```

---

# Python Environment

Create the virtual environment inside the code repository:

```powershell
cd C:\Users\Frederik\Projects\video-tools

py -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the project in editable mode:

```powershell
pip install -e .
```

Editable installation means changes made under:

```text
src\videotools\
```

are immediately reflected in the installed package.

---

# CLI

The goal is to expose the package as a command:

```text
video-tools
```

This can be configured in `pyproject.toml`:

```toml
[project]
name = "video-tools"
version = "0.1.0"

[project.scripts]
video-tools = "videotools.cli:main"
```

After installation:

```powershell
pip install -e .
```

commands can be run without referencing individual Python files.

For example:

```powershell
video-tools journal
```

instead of:

```powershell
python C:\Users\Frederik\Projects\video-tools\src\videotools\journal.py
```

---

# Video Projects

Video projects live under:

```text
C:\Users\Frederik\Videos\Projects\
```

For example:

```text
C:\Users\Frederik\Videos\Projects\vacation-2026
```

A project contains:

```text
vacation-2026\
├── project.toml
├── clips\
├── edits\
├── metadata\
├── exports\
└── journal.json
```

## `clips/`

Original video footage.

Example:

```text
clips\
├── 20260912\
├── 20260913\
└── 20260914\
```

These files should normally be treated as source material and not modified.

## `metadata/`

Machine-generated metadata.

Potential files include:

```text
metadata\
├── clip_report.json
├── markers.json
└── telemetry.json
```

## `edits/`

JSON edit timelines for local rendering and, later, the local web editor.

Example:

```text
edits\
├── 20260913_092145_edit.json
└── 20260913_101422_edit.json
```

The JSON `file` entries remain relative to `clips/`, and the JSON `output`
entry remains relative to `exports/`.

## `exports/`

Rendered output from DaVinci Resolve or other generated video files.

## `journal.json`

Human-entered information about filming sessions, activities, locations, and interesting moments.

## `project.toml`

Project-specific configuration.

---

# Project Configuration

Each project is identified by a `project.toml`.

Example:

```toml
name = "vacation-2026"

[paths]
clips = "clips"
edits = "edits"
metadata = "metadata"
exports = "exports"
journal = "journal.json"

[resolve]
project_name = "vacation-2026"
```

Paths should preferably be relative to the project root.

This makes projects portable and avoids hard-coding paths such as:

```text
C:\Users\Frederik\Videos\Projects\vacation-2026\clips
```

throughout the Python code.

---

# Finding the Current Project

Commands should automatically determine which video project they are operating on.

The convention is:

> The directory containing `project.toml` is the project root.

A helper can search the current directory and its parents:

```python
from pathlib import Path


def find_project_root(start=None):
    current = Path(start or Path.cwd()).resolve()

    for path in [current, *current.parents]:
        if (path / "project.toml").exists():
            return path

    raise RuntimeError(
        "No video project found. "
        "Expected project.toml in this directory or a parent directory."
    )
```

This allows commands to work from anywhere inside a project.

For example:

```powershell
cd C:\Users\Frederik\Videos\Projects\vacation-2026

video-tools journal
```

or even:

```powershell
cd C:\Users\Frederik\Videos\Projects\vacation-2026\clips\20260912

video-tools journal
```

Both resolve to:

```text
C:\Users\Frederik\Videos\Projects\vacation-2026\project.toml
```

---

# Project Object

Project configuration should eventually be represented by a reusable Python object.

For example:

```python
from pathlib import Path
import tomllib


class VideoProject:
    def __init__(self, root):
        self.root = Path(root).resolve()

        config_file = self.root / "project.toml"

        with config_file.open("rb") as f:
            self.config = tomllib.load(f)

    @property
    def name(self):
        return self.config["name"]

    @property
    def clips_dir(self):
        return self.root / self.config["paths"]["clips"]

    @property
    def metadata_dir(self):
        return self.root / self.config["paths"]["metadata"]

    @property
    def exports_dir(self):
        return self.root / self.config["paths"]["exports"]

    @property
    def journal_file(self):
        return self.root / self.config["paths"]["journal"]
```

Other modules then operate on a `VideoProject` rather than containing hard-coded paths.

For example:

```python
project = VideoProject(project_root)

extract_metadata(project.clips_dir)

load_journal(project.journal_file)
```

---

# Journal Conventions

Human-facing date input uses:

```text
YYYYMMDD
```

Example:

```text
20260912
```

Time input uses 24-hour:

```text
HH:MM
```

Example:

```text
15:30
```

Internally, JSON should use standard ISO formatting:

```text
2026-09-12
15:30
2026-09-12T15:30:00
```

Example journal entry:

```json
{
  "date": "2026-09-12",
  "activity": "Bike ride around the coast",
  "location": "Mallorca",
  "start_time": "15:30",
  "end_time": "18:15",
  "tags": ["bike", "coast", "sunset"],
  "highlight": "Fast downhill section near the lighthouse",
  "notes": "Chest mount most of the ride."
}
```

The eventual goal is to correlate journal entries with video timestamps automatically.

For example:

```text
Journal

Bike ride
15:30 -------- 18:15
                  ^
                  |
          GX010123.MP4
          recorded 16:42
```

The clip can then inherit useful context:

```json
{
  "activity": "Bike ride around the coast",
  "location": "Mallorca",
  "tags": ["bike", "coast", "sunset"]
}
```

---

# FFmpeg / ffprobe

`ffprobe` is used for external video inspection.

Verify installation with:

```powershell
ffprobe -version
```

and:

```powershell
where.exe ffprobe
```

Metadata extraction should use `ffprobe` rather than relying on DaVinci Resolve for basic media inspection.

This allows footage to be analyzed before Resolve is opened.

---

# Intended Ingest Workflow

During a trip or shoot:

```text
Camera / SD card
       |
       v
video-tools ingest
       |
       +---- copy originals
       |
       +---- verify copies
       |
       +---- ffprobe
       |
       +---- extract timestamps
       |
       +---- generate metadata
       |
       v
Video project
```

The laptop can therefore act as an ingest and backup station without requiring video editing during the trip.

---

# Intended Editing Workflow

After footage has been collected:

```text
Original footage
       |
       v
Python metadata extraction
       |
       v
clip_report.json
       |
       v
DaVinci Resolve
       |
       v
Review footage manually
       |
       v
Add markers / selections
       |
       v
Export markers as JSON
       |
       v
Python processing
       |
       v
Generate rough-cut instructions
       |
       v
Resolve builds rough cut
       |
       v
Manual creative edit
```

This separates mechanical work from creative decisions.

Python handles:

- files
- metadata
- timestamps
- telemetry
- organization
- searching
- validation
- reusable selections

Resolve handles:

- visual review
- markers
- timelines
- editing
- color
- audio
- rendering

---

# DaVinci Resolve Free

Resolve Free scripts are launched internally from:

```text
Workspace
    > Scripts
        > Utility
```

Utility scripts can be installed under:

```text
C:\ProgramData\Blackmagic Design\
DaVinci Resolve\Fusion\Scripts\Utility\
```

Inside an internally launched script:

```python
resolve = app.GetResolve()

project_manager = resolve.GetProjectManager()
project = project_manager.GetCurrentProject()
```

This has already been tested successfully with DaVinci Resolve 21 Free.

---

# Markers and Reusable Footage

One longer-term goal is to use Resolve markers as structured creative metadata.

For example:

```text
Green   = keep / good shot
Blue    = potential intro
Yellow  = B-roll
Red     = reject / problem
```

A marker might represent:

```json
{
  "frame": 327,
  "color": "Green",
  "name": "Bike passes lighthouse",
  "note": "Good movement and lighting"
}
```

Marker durations can represent selected ranges:

```text
Source clip

──────────████████████──────────────
          ^          ^
          |          |
        start       end

       "Keep this section"
```

Those selections can be exported from Resolve and stored as JSON.

This means useful moments only need to be discovered once and can potentially be reused in future projects.

---

# Future Direction

The project may eventually support:

```text
video-tools init vacation-2026

video-tools ingest E:\

video-tools probe

video-tools journal

video-tools journal list

video-tools report

video-tools backup
```

Potential later functionality includes:

- automatic project creation
- GoPro telemetry extraction
- GPS metadata
- automatic clip tagging
- motion detection
- scene detection
- thumbnails/contact sheets
- reusable footage library
- Resolve marker import/export
- automated rough cuts
- automated render queues

The broader goal is not to replace creative editing.

The goal is to automate repetitive video-management tasks and preserve useful information about footage so that editing in DaVinci Resolve becomes faster and easier.
