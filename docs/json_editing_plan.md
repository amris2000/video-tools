# JSON Editing: Incremental Implementation Plan

This plan adds JSON-driven editing without creating a separate application or
transcoding source footage more than necessary.

## Edit-file conventions

- The edit file is JSON, with an optional `"version": 1`.
- `file` paths are relative to the project's configured `clips` directory.
- `output` is relative to the project's configured `exports` directory.
- Absolute paths and paths that escape those directories are rejected.
- `label` is accepted as non-rendering metadata.
- Future properties such as `speed`, `volume`, and fades produce a clear
  "not supported in version 1" error until implemented.

Example:

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
    }
  ]
}
```

## Increment 1: model and validation

1. Add `VideoProject` to `videotools.project` so new code uses the paths from
   `project.toml`.
2. Add `videotools.edit` with immutable `EditTimeline` and `EditClip` models.
3. Parse JSON and validate its complete version-1 structure.
4. Resolve and validate source and output paths.
5. Add standard-library unit tests that do not require FFmpeg.

Run this increment with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Increment 2: fast renderer — implemented

1. Added `videotools.render` and a `RenderError` exception.
2. Locate `ffmpeg` and `ffprobe` on `PATH` with useful errors.
3. Probe selected sources and verify that streams are compatible for copying.
4. Generate a temporary concat-demuxer file with `file`, `inpoint`, and
   `outpoint` entries in timeline order.
5. Run one FFmpeg stream-copy pass, explicitly mapping the primary video and
   optional primary audio while excluding GoPro data streams.
6. Remove the temporary file automatically, including after failure.
7. Test command construction separately from FFmpeg execution.

Run it from anywhere inside a video-tools project:

```bash
video-tools render edit.json
video-tools render edit.json --mode fast --overwrite
```

Fast mode will be quick but cuts can be affected by keyframe placement.

## Increment 3: accurate renderer — implemented

1. Builds one FFmpeg command containing all selected inputs.
2. Seeks and limits each input to the selected range.
3. Resets timestamps and concatenates video/audio streams in timeline order.
4. Encodes video once with `libx265` and audio once with AAC.
5. Preserves source dimensions and fails clearly when initial format assumptions
   are not met.
6. Uses small synthetic-media integration tests rather than committing large
   camera files.

Accurate rendering is now the default:

```bash
video-tools render edit.json
video-tools render edit.json --mode accurate
video-tools render edit.json --mode fast
```

## Increment 4: CLI and documentation

1. Add `video-tools render EDIT_FILE` to the existing `argparse` CLI.
2. Add `--mode {fast,accurate}`, defaulting to `accurate`.
3. Catch validation and rendering exceptions at the CLI boundary, print a
   concise error to stderr, and return a nonzero exit status.
4. Add `--overwrite` deliberately; never overwrite an export implicitly.
5. Document examples and the fast-versus-accurate trade-off in the README.

## Later extensions

Extend `EditClip` for speed, volume, and fades when their rendering behavior is
implemented. If the timeline later gains title cards, images, transitions, or
multiple tracks, introduce typed timeline elements in a new file-format
version instead of making version 1 ambiguous.
