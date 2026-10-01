# Shared clip browser

The production Clips page renders ClipBrowser in view mode. Both modes use the same API request, loading/error/empty states, responsive grid and ClipCard. Changing mode does not refetch or remount the browser.

Selection is controlled by the consumer. Pass mode="select", selectedClipPaths and onSelectionChange. Paths identify clips relative to the project root; scope selection to projectId (for example, key the consumer by projectId). Switching to view mode hides selection controls while allowing the consumer to preserve its selection.

The development-only route /projects/:projectId/clips/demo demonstrates a consumer switching the same browser between modes and displays the selected paths. It has no edit or timeline integration.

Manual checks with video-tools dev:
- Open a project's clips/demo route; start in view mode, then click Select clips.
- Select multiple clips using mouse and keyboard (Tab, then Space on a checkbox).
- Check the selected border, checkbox, count and consumer paths agree.
- Deselect one clip, clear selection, and verify the consumer updates.
- Switch to view and back; the grid stays the same and selection is preserved.
- Check the normal clips route has no selection controls.
- Change projects while a request is pending; old results must not appear in the new project.
- Check empty projects, missing metadata/thumbnails, and retry after a request failure.

GET /api/projects/{project_id}/clips scans the configured clips directory and reads cached clip_report.json metadata. Missing or malformed cached data is optional. No ffprobe or thumbnail generation runs.
GET /api/projects/{project_id}/thumbnails/{relative_path} streams existing images constrained to the configured metadata directory.

Video playback, edit creation and timeline mutation remain future work.
