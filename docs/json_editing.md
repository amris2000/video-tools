# JSON Video Editing

`video-tools` can render a sequence of selected ranges from source videos into
one MP4 file. The edit is described in JSON, so no graphical editor or project
database is required.

The implementation deliberately supports one ordered track of video clips. It
does not yet implement transitions, effects, titles, music, multiple tracks,
speed changes, or volume automation.

## Requirements

- Python 3.11 or newer
- `ffmpeg` available on `PATH`
- `ffprobe` available on `PATH`
- An initialized `video-tools` project

Check the media tools with:

```bash
ffmpeg -version
ffprobe -version
```

## Project layout

The renderer uses the paths in the project's `project.toml`:

```text
my-project/
├── project.toml
├── edit.json
├── clips/
│   └── 20260912/
│       ├── GX010017.MP4
│       └── GX010018.MP4
└── exports/
```

For example:

```toml
name = "my-project"

[paths]
clips = "clips"
metadata = "metadata"
exports = "exports"
journal = "journal.json"
```

Source paths in the edit file are relative to `clips`. Output paths are
relative to `exports`. This keeps a project portable between computers.

## Edit-file format

A complete version-1 edit file looks like this:

```json
{
  "version": 1,
  "output": "final.mp4",
  "clips": [
    {
      "file": "20260912/GX010017.MP4",
      "start": 2.5,
      "end": 7.8,
      "label": "bike starts moving"
    },
    {
      "file": "20260912/GX010018.MP4",
      "start": 0,
      "end": 4.2
    }
  ]
}
```

### Top-level properties

| Property | Required | Meaning |
| --- | --- | --- |
| `version` | No | File-format version. Omitted means version 1. |
| `output` | Yes | MP4 path relative to the configured exports directory. |
| `clips` | Yes | Non-empty array of clip selections in output order. |

### Clip properties

| Property | Required | Meaning |
| --- | --- | --- |
| `file` | Yes | Source path relative to the configured clips directory. |
| `start` | Yes | Start time in seconds, zero or greater. |
| `end` | Yes | End time in seconds; it must be greater than `start`. |
| `label` | No | Human-readable note with no effect on rendering. |

Timestamps may be integers or decimals. A selection from 2.5 through 7.8 has a
duration of 5.3 seconds.

Both source and output paths must remain inside their configured directories.
Absolute paths and paths such as `../outside.mp4` are rejected. The output must
have an `.mp4` extension.

Properties reserved for future work—`speed`, `volume`, `fade_in`, and
`fade_out`—currently produce an explicit unsupported-property error. They are
not silently ignored.

## Rendering

### Generate a sample edit automatically

To create a ready-to-render example from footage already under `clips/`, run:

```bash
video-tools sample-edit
```

This scans the project recursively, reads clip durations with `ffprobe`, and
creates a new timestamped edit JSON inside `edits/`, for example
`edits/20260913_092145_edit.json`. It chooses up to three videos with matching
stream formats and takes a centered selection of at most three seconds from
each. The generated output name uses the same identifier, for example
`20260913_092145_video.mp4`.

The compatibility grouping means the generated edit works with accurate mode
and, when keyframe-aligned cuts are acceptable, fast mode. Unreadable and very
short clips are skipped. Each run creates a new JSON timeline and does not
replace an older edit file:

```bash
video-tools sample-edit
video-tools render edits/20260913_092145_edit.json
```

The command only writes the JSON instructions. It does not render or modify
source footage.

### Select sample clips interactively

To choose the sample clips and their order yourself, run:

```bash
video-tools select-edit
```

The command lists every usable clip with a number and its duration. Enter one
number at a time in the order the clips should appear. A clip may be selected
more than once. Enter `q`, `quit`, or `done` when the selection is complete.

Each choice receives a centered segment of up to three seconds, just like
`sample-edit`. Clips incompatible with the first selection are rejected with an
explanation so the resulting timeline can be rendered in accurate mode. The
command creates a new timestamped JSON file under `edits/` and sets the JSON
`output` field to the matching timestamped export filename:

```bash
video-tools render edits/20260913_093012_edit.json
```

The JSON `file` values still stay relative to `clips/`, and the JSON `output`
value still stays relative to `exports/`.

## Command help

Run the following from any directory to list all available commands and their
short descriptions:

```bash
video-tools help
```

Standard command-specific help remains available, for example:

```bash
video-tools render --help
video-tools select-edit --help
```

Run the command from the project root or any directory beneath it:

```bash
video-tools render edit.json
```

Accurate rendering is the default. The two modes can also be selected
explicitly:

```bash
video-tools render edit.json --mode accurate
video-tools render edit.json --mode fast
```

An existing output is never overwritten implicitly:

```bash
video-tools render edit.json --overwrite
```

The output from the example above is written to `exports/final.mp4`.

## Accurate mode

Accurate mode is intended when the requested timestamps matter:

```bash
video-tools render edit.json --mode accurate
```

The renderer:

1. Uses `ffprobe` to inspect every unique source file.
2. Checks the selected ranges and stream layouts.
3. Gives FFmpeg one input for each selected range.
4. Seeks to `start` and reads only `end - start` from each input.
5. Resets each selection's video and audio timestamps to zero.
6. Concatenates the selections in JSON order with FFmpeg's concat filter.
7. Encodes the combined video once with `libx265`.
8. Encodes audio once as AAC and writes one MP4.

The initial encoding settings are:

| Setting | Value |
| --- | --- |
| Video codec | HEVC/H.265 using `libx265` |
| Preset | `medium` |
| Quality | CRF 20 |
| MP4 video tag | `hvc1` |
| Audio codec | AAC |
| Audio bitrate | 192 kbps |

The source resolution and pixel format are preserved. For example, GoPro
3840×3360 footage remains 3840×3360 rather than being forced to 16:9.

Accurate mode performs one generation of video encoding. It does not first
transcode every source file into full-size intermediates. Only the selected
ranges are decoded and passed through the final encoder.

In version 1, selected sources must have matching dimensions, frame rates,
pixel formats, and audio layouts. Their compressed input codecs may differ
because accurate mode decodes them before concatenation. A project mixing
landscape and portrait clips, or clips with and without audio, receives a clear
compatibility error rather than being resized or padded automatically.

## Fast mode

Fast mode prioritizes speed and avoids video and audio encoding:

```bash
video-tools render edit.json --mode fast
```

The renderer creates a temporary FFmpeg concat-demuxer file containing the
source files plus `inpoint` and `outpoint` values. FFmpeg then performs one
stream-copy pass using `-c copy`.

This has several useful properties for high-bitrate GoPro footage:

- The original HEVC video remains HEVC.
- Video and audio are not recompressed.
- Full source files are not transcoded.
- Separate encoded intermediate clips are not created.
- The selected packets are copied only into the final output.

Fast mode is not frame-perfect. HEVC video uses inter-frame compression, so an
arbitrary timestamp may fall between keyframes. The resulting cut can contain
extra material around a boundary or begin at the nearest independently
decodable point. Use accurate mode when that difference matters.

Stream copying requires all selected sources to have compatible compressed
stream properties. The renderer compares video codec, dimensions, pixel format,
frame rate, time base, and corresponding audio properties before starting.

## GoPro streams and metadata

GoPro MP4 files can contain a primary video stream, an audio stream, thumbnail
or preview material, and GPMF telemetry/data streams.

The timeline renderer deliberately selects:

- The first normal video stream
- The first audio stream, when present

It excludes subtitle and data streams from the output. Consequently, GPMF GPS
and motion telemetry are not preserved in the rendered MP4. The original files
under `clips` are not modified and retain all of their metadata.

This is intentional for the first editing version: telemetry timestamps would
need to be trimmed and rebased correctly for every selection before it could be
meaningfully preserved.

## Validation and errors

The edit is validated before FFmpeg starts. Errors identify the affected field
where possible. Examples include:

```text
clips must be a non-empty array.
clips[1].end must be greater than clips[1].start.
Source video does not exist: ...
clips[0].end (18.5) exceeds the source duration (17 seconds): ...
Output already exists: ... Use --overwrite to replace it.
ffmpeg was not found on PATH. Make sure FFmpeg is installed.
```

The CLI prints expected validation and rendering failures as `ERROR: ...` and
returns a nonzero exit status. If FFmpeg fails after creating a partial output,
that incomplete output is removed. Temporary concat files are also removed,
including after failures.

## Code structure

The feature is integrated with the existing package:

```text
src/videotools/
├── cli.py       # render command and user-facing error handling
├── project.py   # project discovery, configuration, and configured paths
├── edit.py      # immutable timeline model, JSON parsing, and validation
├── render.py    # probing, compatibility checks, and FFmpeg execution
└── media.py     # supported source extensions
```

`VideoProject` resolves the paths configured by `project.toml`.
`load_edit_timeline` converts untrusted JSON into immutable `EditTimeline` and
`EditClip` objects. Rendering functions therefore receive validated paths and
timestamps rather than raw dictionaries.

`render_fast` and `render_accurate` share source probing, duration checks,
executable lookup, output protection, and FFmpeg error handling. Their command
construction remains separate because stream copying and filtered encoding are
fundamentally different operations.

## Tests

Run all tests from the repository root:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

The tests use Python's standard `unittest` library and do not add a third-party
dependency. They cover:

- JSON structure and timestamp validation
- Safe source and output path resolution
- Missing source files
- Unsupported future properties
- Concat-list ordering and ranges
- FFmpeg command construction
- ffprobe response and failure handling
- Source-duration limits
- Fast-mode stream compatibility
- Accurate filter graphs with and without audio
- Accurate-mode format compatibility

Small synthetic videos can be generated for end-to-end FFmpeg smoke tests;
large camera files do not need to be committed to the repository.

## Current limitations and extension path

Version 1 intentionally represents one ordered sequence of clip ranges. The
following are not implemented:

- Transitions or crossfades
- Titles and text cards
- Still images
- Speed changes
- Per-clip volume and fades
- Music or separate audio tracks
- Multiple video tracks
- Automatic scaling, padding, or frame-rate conversion
- Hardware-specific encoders
- Telemetry preservation

Per-clip operations such as speed and volume can later become fields on
`EditClip` once their FFmpeg filters and validation rules exist. Different
timeline element types—titles, images, transitions, and audio—should be added
through a new file-format version with typed elements. That avoids changing the
meaning of existing version-1 edit files.
