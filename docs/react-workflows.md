# React Editing and Exports

The React project workflows are available at:

- `/projects/<project-id>/editor`
- `/projects/<project-id>/render`
- `/projects/<project-id>/exports`

They use project-scoped FastAPI routes and the existing configured project paths. The CLI remains an independent interface over the same edit, render, and social-conversion functionality. The standalone `video-tools editor` remains available.

## Edit timelines

Edits continue to use the existing version-1 JSON format documented in [json_editing.md](json_editing.md). The `clips` array is ordered; repeated `file` values are valid separate occurrences. In the React editor, each loaded or added timeline occurrence receives a temporary UUID. That UUID is used for selection, reordering, removal, trimming, and React keys, and is not written to JSON. Saving preserves the ordered entries and their individual timestamps, labels, and source paths.

The Editor reuses the Clips page's `ClipBrowser` in selection mode. Clip catalog paths are translated from project-relative paths to the configured clips-directory-relative paths required by version 1 of the edit format.

## Rendering and social conversion

Rendering is initiated from the Render page and uses the existing accurate or fast Python renderer. Social conversion is initiated from Exports and uses the presets and framing modes advertised by the backend. Completed normal and social videos are streamed from their separate configured directories with byte-range support for browser playback and seeking.

A single in-process worker handles rendering and social conversion. Only one media operation may be active at a time. Job state is held in memory; it is lost if the application exits or restarts, and jobs are not resumed after restart. This is intentionally local and does not use a database or external job service.

## API routes

- `GET/POST /api/projects/{project_id}/edits`
- `GET/PUT/DELETE /api/projects/{project_id}/edits/{filename}`
- `POST /api/projects/{project_id}/edits/{filename}/rename`
- `GET /api/projects/{project_id}/media/{relative_path}`
- `GET /api/projects/{project_id}/exports`
- `GET /api/projects/{project_id}/exports/{filename}`
- `GET /api/projects/{project_id}/social-exports/{filename}`
- `POST /api/projects/{project_id}/renders`
- `POST /api/projects/{project_id}/social-exports`
- `GET /api/projects/{project_id}/jobs/{job_id}`

Media and export paths are resolved under the configured project directories. Video routes stream files and support single HTTP byte ranges; they do not read entire videos into memory.
