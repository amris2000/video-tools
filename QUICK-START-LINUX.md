# video-tools — Linux / Arch

## First-time setup

Install the required system packages:

```bash
sudo pacman -Syu ffmpeg perl-image-exiftool python python-pip
```

Verify FFmpeg, ffprobe, and ExifTool:

```bash
ffmpeg -version
ffprobe -version
exiftool -ver
```

Go to the `video-tools` repository:

```bash
cd ~/Projects/video-tools
```

Create the Python virtual environment if it does not already exist:

```bash
python -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install `video-tools` in editable mode:

```bash
python -m pip install -e .
```

Verify the CLI:

```bash
video-tools --help
```

---

# Starting a new video project

Activate the `video-tools` environment:

```bash
cd ~/Projects/video-tools
source .venv/bin/activate
```

Go to the directory containing your video projects:

```bash
cd ~/Videos/Projects
```

Create a new project:

```bash
video-tools init test-project
```

This creates:

```text
test-project/
├── project.toml
├── journal.json
├── clips/
├── edits/
├── metadata/
│   └── thumbnails/
└── exports/
```

You do **not** need to run `mkdir test-project` first. The `video-tools init` command creates the project directory for you.

---

# Working on an existing project

First activate `video-tools`:

```bash
cd ~/Projects/video-tools
source .venv/bin/activate
```

Then move to the video project:

```bash
cd ~/Videos/Projects/test-project
```

Check that `video-tools` recognizes the current project:

```bash
video-tools project
```

It should print something similar to:

```text
Project: /home/frederik/Videos/Projects/test-project
```

---

# Normal workflow

Copy new GoPro footage into:

```text
clips/
```

Then organize the loose clips into date folders:

```bash
video-tools organize
```

Generate thumbnails:

```bash
video-tools thumbnails
```

Analyze the clips and regenerate the project metadata:

```bash
video-tools probe
```

The normal sequence is therefore:

```bash
video-tools organize
video-tools thumbnails
video-tools probe
```

Afterward the project will look roughly like:

```text
test-project/
├── project.toml
├── journal.json
│
├── clips/
│   ├── 20260910/
│   │   ├── GX010001.MP4
│   │   └── GX010002.MP4
│   └── 20260911/
│       └── GX010003.MP4
│
├── edits/
│   └── 20260913_092145_edit.json
│
├── metadata/
│   ├── clip_report.json
│   ├── clip_report.html
│   └── thumbnails/
│       ├── GX010001-....webp
│       ├── GX010002-....webp
│       └── GX010003-....webp
│
└── exports/
	└── 20260913_092145_video.mp4
```

`clip_report.json` contains the metadata used by the React frontend, including video information, thumbnails, journal matches, GoPro telemetry detection, and GPS information when available.

To create a new edit timeline JSON and then render it:

```bash
video-tools sample-edit
video-tools render
```

Each `sample-edit` or `select-edit` run creates a new timestamped file inside
`edits/` rather than replacing a fixed filename in the project root.

`video-tools render` then interactively asks for the render mode and which edit
file to render, and writes a fresh timestamped MP4 to `exports/` on every run.

---

# Journal

Add a journal entry:

```bash
video-tools journal add
```

List existing journal entries:

```bash
video-tools journal list
```

After changing journal information, regenerate the report:

```bash
video-tools probe
```

---

# Thumbnail regeneration

Existing thumbnails are skipped by default:

```bash
video-tools thumbnails
```

To regenerate all thumbnails:

```bash
video-tools thumbnails --force
```

---

# Quick vacation workflow

At the start of a terminal session:

```bash
cd ~/Projects/video-tools
source .venv/bin/activate
```

Then:

```bash
cd ~/Videos/Projects/vacation-2026
```

After copying footage from the GoPro SD card into `clips/`:

```bash
video-tools organize
video-tools thumbnails
video-tools probe
```

Done.

The original video files stay local. `video-tools` organizes them and generates the metadata and thumbnails needed by the rest of the workflow.
