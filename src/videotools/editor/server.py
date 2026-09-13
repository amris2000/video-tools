from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import mimetypes
from pathlib import Path
import shutil
from subprocess import CalledProcessError
from typing import Any
from urllib.parse import unquote, urlparse
import webbrowser

from videotools.edit import EditValidationError
from videotools.edit_files import (
    create_edit_document,
    create_empty_edit_document,
    delete_edit_file,
    load_edit_document,
    list_edit_files,
    output_name_for_edit_filename,
    rename_edit_file,
    resolve_edit_file,
    save_edit_document,
    suggested_edit_filename,
    validate_edit_filename,
)
from videotools.editor_validation import validate_editor_document
from videotools.media import VIDEO_EXTENSIONS
from videotools.metadata import load_existing_report, probe_video
from videotools.project import VideoProject

STATIC_ROOT = files("videotools.editor").joinpath("static")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
STREAM_CHUNK_SIZE = 1024 * 256
CLIENT_DISCONNECT_ERRORS = (
    BrokenPipeError,
    ConnectionResetError,
    ConnectionAbortedError,
)


@dataclass(frozen=True)
class ClipCatalogEntry:
    file: str
    name: str
    duration: float | None


class EditorHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        project: VideoProject,
    ) -> None:
        super().__init__(server_address, EditorRequestHandler)
        self.project = project
        self.clip_catalog = _load_clip_catalog(project)
        self.clip_durations = {
            entry.file: entry.duration
            for entry in self.clip_catalog
        }


class EditorRequestHandler(BaseHTTPRequestHandler):
    server: EditorHTTPServer

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == "/":
                self._serve_static_file("index.html")
            elif path.startswith("/static/"):
                self._serve_static_file(path.removeprefix("/static/"))
            elif path == "/api/project":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "name": self.server.project.name,
                        "root": str(self.server.project.root),
                    },
                )
            elif path == "/api/edits":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "edits": [
                            {"filename": edit_file.name}
                            for edit_file in list_edit_files(self.server.project)
                        ]
                    },
                )
            elif path == "/api/edits/defaults":
                filename = suggested_edit_filename(self.server.project)
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "filename": filename,
                        "output": output_name_for_edit_filename(filename),
                    },
                )
            elif path == "/api/clips":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "clips": [entry.__dict__ for entry in self.server.clip_catalog]
                    },
                )
            elif path.startswith("/api/edits/"):
                filename = self._edit_filename_from_path(path)
                document = load_edit_document(self.server.project, filename)
                document = validate_editor_document(
                    document,
                    self.server.project,
                    durations=self.server.clip_durations,
                )
                self._send_json(HTTPStatus.OK, document)
            elif path.startswith("/media/"):
                self._serve_media(path.removeprefix("/media/"))
            else:
                self._send_error_json(HTTPStatus.NOT_FOUND, "Not found.")
        except CLIENT_DISCONNECT_ERRORS:
            return
        except (ValueError, EditValidationError) as error:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(error))
        except FileNotFoundError as error:
            self._send_error_json(HTTPStatus.NOT_FOUND, str(error))
        except OSError as error:
            self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(error))

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == "/api/edits":
                payload = self._read_json_body()
                filename = validate_edit_filename(payload.get("filename", ""))
                output = payload.get("output") or output_name_for_edit_filename(filename)
                document = validate_editor_document(
                    create_empty_edit_document(filename, output),
                    self.server.project,
                    durations=self.server.clip_durations,
                )
                create_edit_document(self.server.project, filename, document)
                self._send_json(
                    HTTPStatus.CREATED,
                    {"filename": filename, "document": document},
                )
            elif path.endswith("/rename"):
                current = self._edit_filename_from_action_path(path, "rename")
                payload = self._read_json_body()
                new_filename = validate_edit_filename(payload.get("filename", ""))
                destination = rename_edit_file(self.server.project, current, new_filename)
                self._send_json(
                    HTTPStatus.OK,
                    {"filename": destination.name},
                )
            elif path.endswith("/save-as"):
                current = self._edit_filename_from_action_path(path, "save-as")
                current_file = resolve_edit_file(self.server.project, current)
                if not current_file.exists():
                    raise FileNotFoundError(f"Edit file does not exist: {current_file}")
                payload = self._read_json_body()
                filename = validate_edit_filename(payload.get("filename", ""))
                document = validate_editor_document(
                    payload.get("document"),
                    self.server.project,
                    durations=self.server.clip_durations,
                )
                create_edit_document(self.server.project, filename, document)
                self._send_json(
                    HTTPStatus.CREATED,
                    {"filename": filename, "document": document},
                )
            else:
                self._send_error_json(HTTPStatus.NOT_FOUND, "Not found.")
        except CLIENT_DISCONNECT_ERRORS:
            return
        except FileExistsError as error:
            self._send_error_json(HTTPStatus.CONFLICT, str(error))
        except (ValueError, EditValidationError) as error:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(error))
        except FileNotFoundError as error:
            self._send_error_json(HTTPStatus.NOT_FOUND, str(error))
        except OSError as error:
            self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(error))

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path.startswith("/api/edits/"):
                filename = self._edit_filename_from_path(path)
                payload = self._read_json_body()
                document = validate_editor_document(
                    payload.get("document"),
                    self.server.project,
                    durations=self.server.clip_durations,
                )
                save_edit_document(self.server.project, filename, document)
                self._send_json(
                    HTTPStatus.OK,
                    {"filename": filename, "document": document},
                )
            else:
                self._send_error_json(HTTPStatus.NOT_FOUND, "Not found.")
        except CLIENT_DISCONNECT_ERRORS:
            return
        except (ValueError, EditValidationError) as error:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(error))
        except FileNotFoundError as error:
            self._send_error_json(HTTPStatus.NOT_FOUND, str(error))
        except OSError as error:
            self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(error))

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path.startswith("/api/edits/"):
                filename = self._edit_filename_from_path(path)
                delete_edit_file(self.server.project, filename)
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
            else:
                self._send_error_json(HTTPStatus.NOT_FOUND, "Not found.")
        except CLIENT_DISCONNECT_ERRORS:
            return
        except (ValueError, EditValidationError) as error:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(error))
        except FileNotFoundError as error:
            self._send_error_json(HTTPStatus.NOT_FOUND, str(error))
        except OSError as error:
            self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(error))

    def log_message(self, format: str, *args: object) -> None:
        return

    def _serve_static_file(self, relative_path: str) -> None:
        path = _resolve_static_path(relative_path)
        content_type, _ = mimetypes.guess_type(str(path))
        data = path.read_bytes()

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_media(self, encoded_relative_path: str) -> None:
        media_file = _resolve_media_path(self.server.project, unquote(encoded_relative_path))
        content_type, _ = mimetypes.guess_type(str(media_file))
        file_size = media_file.stat().st_size
        range_header = self.headers.get("Range")

        if range_header:
            start, end = _parse_range_header(range_header, file_size)
            if start is None or end is None:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.end_headers()
                return

            length = end - start + 1
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(length))
            self.end_headers()
            _stream_file(self.wfile, media_file, start=start, length=length)
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(file_size))
        self.end_headers()
        _stream_file(self.wfile, media_file, start=0, length=file_size)

    def _read_json_body(self) -> dict[str, Any]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Content-Length must be an integer.") from error

        try:
            payload = json.loads(self.rfile.read(content_length) or b"{}")
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid JSON body: line {error.lineno}, column {error.colno}: {error.msg}"
            ) from error

        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")

        return payload

    def _edit_filename_from_path(self, path: str) -> str:
        parts = path.split("/")
        if len(parts) != 4 or not parts[3]:
            raise ValueError("A valid edit filename is required.")
        return validate_edit_filename(unquote(parts[3]))

    def _edit_filename_from_action_path(self, path: str, action: str) -> str:
        parts = path.split("/")
        if len(parts) != 5 or parts[4] != action or not parts[3]:
            raise ValueError("A valid edit filename is required.")
        return validate_edit_filename(unquote(parts[3]))

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except CLIENT_DISCONNECT_ERRORS:
            return

    def _send_error_json(self, status: HTTPStatus, message: str) -> None:
        self._send_json(status, {"error": message})


def start_editor_server(
    project: VideoProject,
    *,
    host: str = DEFAULT_HOST,
    preferred_port: int = DEFAULT_PORT,
) -> EditorHTTPServer:
    ports_to_try = [preferred_port + offset for offset in range(10)] + [0]

    last_error: OSError | None = None
    for port in ports_to_try:
        try:
            return EditorHTTPServer((host, port), project)
        except OSError as error:
            last_error = error
            continue

    assert last_error is not None
    raise last_error


def run_editor_server(project: VideoProject) -> None:
    server = start_editor_server(project)
    host, port = server.server_address[:2]
    url = f"http://{host}:{port}"

    print("Video timeline editor running for:")
    print(f"  {project.root}")
    print()
    print("Open:")
    print(f"  {url}")
    print()
    print("Press Ctrl+C to stop.")

    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _resolve_static_path(relative_path: str) -> Path:
    candidate = Path(unquote(relative_path))
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("Invalid static asset path.")

    static_root = Path(str(STATIC_ROOT)).resolve()
    target = (static_root / candidate).resolve()
    if not target.is_relative_to(static_root) or not target.is_file():
        raise FileNotFoundError(f"Static asset not found: {relative_path}")

    return target


def _resolve_media_path(project: VideoProject, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("Media path must stay inside the project's clips directory.")

    target = (project.clips_dir / candidate).resolve()
    if not target.is_relative_to(project.clips_dir):
        raise ValueError("Media path must stay inside the project's clips directory.")
    if target.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError("Media path is not a supported video type.")
    if not target.is_file():
        raise FileNotFoundError(f"Media file does not exist: {target}")

    return target


def _parse_range_header(value: str, file_size: int) -> tuple[int | None, int | None]:
    if not value.startswith("bytes=") or "," in value:
        return None, None

    start_text, _, end_text = value.removeprefix("bytes=").partition("-")

    try:
        if start_text and end_text:
            start = int(start_text)
            end = int(end_text)
        elif start_text:
            start = int(start_text)
            end = file_size - 1
        elif end_text:
            suffix_length = int(end_text)
            if suffix_length <= 0:
                return None, None
            start = max(0, file_size - suffix_length)
            end = file_size - 1
        else:
            return None, None
    except ValueError:
        return None, None

    if start < 0 or end < start or start >= file_size:
        return None, None

    return start, min(end, file_size - 1)


def _stream_file(target, media_file: Path, *, start: int, length: int) -> None:
    remaining = length

    with media_file.open("rb") as handle:
        handle.seek(start)

        while remaining > 0:
            chunk = handle.read(min(STREAM_CHUNK_SIZE, remaining))
            if not chunk:
                break
            target.write(chunk)
            remaining -= len(chunk)


def _load_clip_catalog(project: VideoProject) -> list[ClipCatalogEntry]:
    report = load_existing_report(project.metadata_dir / "clip_report.json")
    clips: list[ClipCatalogEntry] = []

    if report and isinstance(report.get("clips"), list):
        for clip in report["clips"]:
            entry = _clip_from_report(project, clip)
            if entry is not None:
                clips.append(entry)

        if clips:
            return sorted(clips, key=lambda item: item.file)

    for path in sorted(project.clips_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue

        duration = _probe_duration(path)
        clips.append(
            ClipCatalogEntry(
                file=path.relative_to(project.clips_dir).as_posix(),
                name=path.name,
                duration=duration,
            )
        )

    unknown_durations = [entry.file for entry in clips if entry.duration is None]
    if unknown_durations:
        raise RuntimeError(
            "Could not determine source durations for editor preview. "
            "Run video-tools probe or make sure ffprobe is available."
        )

    return clips


def _clip_from_report(project: VideoProject, clip: dict[str, Any]) -> ClipCatalogEntry | None:
    relative_path = clip.get("relative_path")
    duration = clip.get("duration")

    if not isinstance(relative_path, str):
        return None

    absolute = (project.root / relative_path).resolve()
    if not absolute.is_relative_to(project.clips_dir) or not absolute.is_file():
        return None

    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        duration = None

    return ClipCatalogEntry(
        file=absolute.relative_to(project.clips_dir).as_posix(),
        name=absolute.name,
        duration=round(float(duration), 3) if duration is not None else None,
    )


def _probe_duration(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None

    try:
        info = probe_video(path)
    except (CalledProcessError, RuntimeError, OSError, json.JSONDecodeError):
        return None

    format_info = info.get("format", {})

    try:
        return round(float(format_info.get("duration") or 0.0), 3)
    except (TypeError, ValueError):
        return None