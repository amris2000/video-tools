# DaVinci Resolve Free + Python Project Workflow

This is the workflow we established for building small, scriptable
video-editing projects with **DaVinci Resolve Free on Windows**, Python,
and FFmpeg/ffprobe.

## 1. Architecture

The useful split is:

``` text
External Python environment
    |
    |-- filesystem work
    |-- ffprobe media analysis
    |-- metadata / telemetry processing
    |-- JSON report generation
    v
clip_report.json
    |
    v
DaVinci Resolve Free
    |
    |-- Workspace > Scripts
    |-- internal Python script
    |-- app.GetResolve()
    v
Media Pool / timeline / edit / render
```

Resolve Free does **not** give our external Python process the same
direct scripting connection as Resolve Studio. Instead, Resolve scripts
are launched internally from **Workspace \> Scripts**.

Inside those scripts, get Resolve with:

``` python
resolve = app.GetResolve()
```

Do not rely on this external-style connection for the Free edition:

``` python
DaVinciResolveScript.scriptapp("Resolve")
```

------------------------------------------------------------------------

# 2. Starting a New Project

Assume the new project is called `my-video`.

## Create the working folders

For example:

``` text
C:\Users\Frederik\Videos\Projects\my-video\
    clips\
    scripts\
    exports\
```

From PowerShell:

``` powershell
cd C:\Users\Frederik\Videos\Projects
mkdir my-video
cd my-video

mkdir clips
mkdir scripts
mkdir exports
```

Put the original footage in:

``` text
my-video\clips\
```

Keep generated exports out of the source folder.

------------------------------------------------------------------------

# 3. Create the Python Environment

From the project root:

``` powershell
py -m venv .venv
```

Activate it:

``` powershell
.\.venv\Scripts\Activate.ps1
```

Your prompt should now start with something similar to:

``` text
(.venv) PS C:\Users\Frederik\Videos\Projects\my-video>
```

When running project scripts, prefer:

``` powershell
python .\scripts\some_script.py
```

rather than:

``` powershell
py .\scripts\some_script.py
```

This makes it clear that the activated virtual environment's Python is
being used.

------------------------------------------------------------------------

# 4. Verify FFmpeg / ffprobe

The external analysis stage uses `ffprobe`.

Check:

``` powershell
ffprobe -version
```

and:

``` powershell
where.exe ffprobe
```

If Windows cannot find it, add the FFmpeg `bin` directory to PATH.

For the installation used while developing this workflow, the directory
was similar to:

``` text
C:\Users\Frederik\AppData\Local\Microsoft\WinGet\Packages\
Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\
ffmpeg-9.0.1-full_build\bin
```

A temporary PowerShell PATH addition looks like:

``` powershell
$env:Path += ";C:\path\to\ffmpeg\bin"
```

Then test again:

``` powershell
ffprobe -version
```

------------------------------------------------------------------------

# 5. Create the Resolve Project

Open DaVinci Resolve and create a new project.

For clarity, use the same name as the filesystem project:

``` text
Filesystem:  my-video
Resolve:     my-video
```

This is not technically required, but makes projects much easier to
reason about.

------------------------------------------------------------------------

# 6. External Preflight / Analysis

Create an external Python script such as:

``` text
my-video\scripts\diagnose_clips.py
```

Its job is to inspect everything in:

``` text
my-video\clips\
```

using `ffprobe`.

Useful information to collect includes:

-   filename
-   absolute path
-   duration
-   resolution
-   frame rate
-   video codec
-   video profile
-   pixel format
-   audio codec
-   audio sample rate
-   audio channels

The script should write a machine-readable report:

``` text
my-video\clip_report.json
```

Example:

``` json
{
  "summary": {
    "clip_count": 3,
    "recommended_width": 1280,
    "recommended_height": 720,
    "recommended_fps": 29.97
  },
  "clips": [
    {
      "name": "clip01.mp4",
      "path": "C:\\Users\\Frederik\\Videos\\Projects\\my-video\\clips\\clip01.mp4",
      "width": 1280,
      "height": 720,
      "fps": 29.97,
      "codec": "h264",
      "pixel_format": "yuv420p",
      "duration": 18.77
    }
  ]
}
```

Run the preflight with:

``` powershell
python .\scripts\diagnose_clips.py
```

Before opening/building a timeline, inspect the output for unexpected
frame rates, resolutions, codecs, or missing audio.

------------------------------------------------------------------------

# 7. Install the Resolve-Side Script

Resolve Free can execute scripts internally from the Workspace menu.

For a utility script available throughout Resolve, place it in:

``` text
C:\ProgramData\Blackmagic Design\
DaVinci Resolve\Fusion\Scripts\Utility\
```

For example:

``` text
Build Timeline From Report.py
```

If a newly created script does not appear, restart Resolve.

It should then be available from:

``` text
Workspace
  > Scripts
    > Utility
      > Build Timeline From Report
```

------------------------------------------------------------------------

# 8. Connecting to Resolve Free

Inside a script launched from `Workspace > Scripts`, use:

``` python
resolve = app.GetResolve()

if resolve is None:
    raise RuntimeError("Could not get Resolve.")

project_manager = resolve.GetProjectManager()
project = project_manager.GetCurrentProject()

if project is None:
    raise RuntimeError("No Resolve project is open.")

media_pool = project.GetMediaPool()
```

This is the key connection pattern for this workflow.

------------------------------------------------------------------------

# 9. Build the Timeline From the Report

The Resolve-side script can read:

``` text
clip_report.json
```

and use it to:

1.  determine the intended resolution;
2.  determine the intended frame rate;
3.  configure the project;
4.  import the exact analyzed media files;
5.  create a timeline;
6.  append the clips;
7.  make the timeline current;
8.  switch Resolve to the Edit page.

Conceptually:

``` text
clip_report.json
       |
       v
Read recommended settings
       |
       v
Configure Resolve project
       |
       v
Import analyzed files
       |
       v
Create timeline
       |
       v
Append clips
       |
       v
Start editing
```

------------------------------------------------------------------------

# 10. Clean Test Runs

During development it is useful to clear the test project before
rebuilding.

A helper can delete timelines and root-level Media Pool clips:

``` python
def clear_workspace(project):
    media_pool = project.GetMediaPool()
    root_folder = media_pool.GetRootFolder()

    timelines = []

    for i in range(1, project.GetTimelineCount() + 1):
        timeline = project.GetTimelineByIndex(i)

        if timeline:
            timelines.append(timeline)

    if timelines:
        media_pool.DeleteTimelines(timelines)

    clips = root_folder.GetClipList()

    if clips:
        media_pool.DeleteClips(clips)

    print("Workspace cleared.")
```

Control it with a development flag:

``` python
CLEAR_PROJECT_FIRST = True

if CLEAR_PROJECT_FIRST:
    clear_workspace(project)
```

**Warning:** this is destructive. Keep it restricted to disposable/test
projects.

Once real editing starts, change it to:

``` python
CLEAR_PROJECT_FIRST = False
```

------------------------------------------------------------------------

# 11. Normal Startup Routine

For a fresh editing project, the practical routine is:

``` text
1. Create project directory
2. Create clips/, scripts/, exports/
3. Create and activate .venv
4. Copy footage into clips/
5. Verify ffprobe works
6. Create/open matching Resolve project
7. Run diagnose_clips.py
8. Inspect clip_report.json / warnings
9. Run Build Timeline From Report from Workspace > Scripts
10. Begin the creative edit
```

In PowerShell, the recurring external part is approximately:

``` powershell
cd C:\Users\Frederik\Videos\Projects\my-video

.\.venv\Scripts\Activate.ps1

ffprobe -version

python .\scripts\diagnose_clips.py
```

Then move to Resolve and run the internal build script.

------------------------------------------------------------------------

# 12. Why Use This Workflow?

The main advantage is that **media analysis and video editing are
separate jobs**.

Python + ffprobe is excellent at:

-   inspecting hundreds of files;
-   finding inconsistencies;
-   processing metadata;
-   analyzing GoPro telemetry;
-   calculating statistics;
-   renaming and organizing;
-   generating manifests;
-   eventually running computer-vision or audio analysis.

Resolve is excellent at:

-   Media Pool organization;
-   timeline creation;
-   editing;
-   markers;
-   effects;
-   color;
-   audio;
-   rendering.

The JSON report becomes the contract between the two sides.

Instead of making Resolve figure everything out, Python can say:

> These are the files, these are their properties, these are the
> warnings, and this is how I recommend initializing the edit.

Resolve then performs the editing operations.

------------------------------------------------------------------------

# 13. Good Next Experiments

## A. Preflight warnings

Make `diagnose_clips.py` detect:

-   mixed frame rates;
-   mixed resolutions;
-   clips without audio;
-   unusual codecs;
-   portrait vs landscape footage;
-   very short clips;
-   corrupt/unreadable files.

Example:

``` text
PRE-FLIGHT

✓ clip01.mp4   1920x1080  29.97 fps
✓ clip02.mp4   1920x1080  29.97 fps
! clip03.mp4   3840x2160  59.94 fps

WARNING:
Mixed frame rates detected.
```

This is probably the best immediate next step.

## B. Automatic Media Pool bins

Have Python classify clips and have Resolve create bins such as:

``` text
Media Pool
├── GoPro
├── Drone
├── Phone
├── Audio
├── B-Roll
└── Unknown
```

## C. Automatic markers

Generate markers from external analysis.

Examples:

-   scene changes;
-   loud audio events;
-   motion peaks;
-   GPS locations;
-   speed thresholds;
-   interesting GoPro telemetry events.

Then have the Resolve script add those markers to clips or timelines.

## D. GoPro telemetry

For actual GoPro footage, extract telemetry and augment
`clip_report.json`:

``` json
{
  "max_speed_kmh": 47.2,
  "gps": true,
  "motion_score": 0.83
}
```

That creates possibilities such as:

``` text
speed > 40 km/h
        ↓
create Resolve marker
        ↓
candidate highlight
```

## E. Automatic rough cuts

External Python can calculate candidate sections:

``` json
{
  "highlights": [
    {
      "clip": "GX010042.MP4",
      "start": 31.5,
      "end": 39.2,
      "reason": "high motion"
    }
  ]
}
```

Resolve can then create a rough-cut timeline from those ranges.

This is where the workflow starts becoming an actual editing assistant
rather than merely an importer.

## F. Automatic rendering

Once the timeline is finished, scripts can help standardize export jobs
such as:

``` text
Master
YouTube
Vertical / Shorts
Preview
```

The goal is to automate repetitive setup while leaving the creative
decisions in Resolve.

------------------------------------------------------------------------

# 14. Longer-Term Goal

A useful end-state for a GoPro project could be:

``` text
Copy GoPro card
      |
      v
Python ingest
      |
      +--> inspect codecs
      +--> extract telemetry
      +--> detect scenes
      +--> score motion
      +--> identify GPS/speed events
      +--> generate thumbnails
      |
      v
project_report.json
      |
      v
Resolve build script
      |
      +--> create bins
      +--> import footage
      +--> configure timeline
      +--> add markers
      +--> build candidate highlights
      |
      v
You make creative decisions
      |
      v
Resolve export script
      |
      +--> master
      +--> YouTube
      +--> social versions
```

That preserves the part humans are good at --- deciding what is
interesting and how the video should feel --- while scripting the
repetitive mechanical work.
