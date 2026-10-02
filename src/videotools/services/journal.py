from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from videotools.journal import load_journal, save_journal
from videotools.project import VideoProject


def _today_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _normalize_entry(raw: dict) -> tuple[dict, bool]:
    changed = False

    entry_id = raw.get("id")
    if not isinstance(entry_id, str) or not entry_id.strip():
        entry_id = str(uuid4())
        changed = True

    logged_at = raw.get("logged_at")
    if not isinstance(logged_at, str) or not logged_at.strip():
        logged_at = datetime.now().isoformat(timespec="seconds")
        changed = True

    date = raw.get("date")
    if not isinstance(date, str) or not date.strip():
        date = _today_date()
        changed = True

    activity = raw.get("activity")
    if not isinstance(activity, str):
        activity = ""
        changed = True

    location = raw.get("location")
    if location is not None and not isinstance(location, str):
        location = None
        changed = True

    start_time = raw.get("start_time")
    if start_time is not None and not isinstance(start_time, str):
        start_time = None
        changed = True

    end_time = raw.get("end_time")
    if end_time is not None and not isinstance(end_time, str):
        end_time = None
        changed = True

    highlight = raw.get("highlight")
    if highlight is not None and not isinstance(highlight, str):
        highlight = None
        changed = True

    notes = raw.get("notes")
    if notes is not None and not isinstance(notes, str):
        notes = None
        changed = True

    tags_raw = raw.get("tags", [])
    if isinstance(tags_raw, list):
        tags = [str(tag).strip().lower() for tag in tags_raw if str(tag).strip()]
        if tags != tags_raw:
            changed = True
    else:
        tags = []
        changed = True

    return (
        {
            "id": entry_id,
            "date": date,
            "activity": activity,
            "location": location,
            "start_time": start_time,
            "end_time": end_time,
            "tags": tags,
            "highlight": highlight,
            "notes": notes,
            "logged_at": logged_at,
        },
        changed,
    )


def _journal_path(project: VideoProject) -> Path:
    path = project.journal_file
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_journal(project: VideoProject) -> tuple[dict, bool]:
    journal = load_journal(_journal_path(project))
    entries = journal.get("entries", [])

    if not isinstance(entries, list):
        journal["entries"] = []
        return journal, True

    normalized: list[dict] = []
    changed = False

    for raw in entries:
        if not isinstance(raw, dict):
            changed = True
            continue

        entry, entry_changed = _normalize_entry(raw)
        normalized.append(entry)
        changed = changed or entry_changed

    if normalized != entries:
        changed = True

    journal["entries"] = normalized
    return journal, changed


def _save_journal(project: VideoProject, journal: dict) -> None:
    save_journal(_journal_path(project), journal)


def list_entries(project: VideoProject) -> list[dict]:
    journal, changed = _load_journal(project)

    if changed:
        _save_journal(project, journal)

    entries = journal.get("entries", [])

    return sorted(
        entries,
        key=lambda entry: (
            entry.get("date") or "",
            entry.get("start_time") or "",
            entry.get("logged_at") or "",
        ),
    )


def create_entry(
    project: VideoProject,
    payload: dict,
) -> dict:
    journal, changed = _load_journal(project)

    entry = {
        "id": str(uuid4()),
        "date": payload["date"],
        "activity": payload["activity"],
        "location": payload.get("location"),
        "start_time": payload.get("start_time"),
        "end_time": payload.get("end_time"),
        "tags": [tag.strip().lower() for tag in payload.get("tags", []) if tag.strip()],
        "highlight": payload.get("highlight"),
        "notes": payload.get("notes"),
        "logged_at": datetime.now().isoformat(timespec="seconds"),
    }

    journal["entries"].append(entry)

    _save_journal(project, journal)

    if changed:
        _save_journal(project, journal)

    return entry


def update_entry(
    project: VideoProject,
    entry_id: str,
    payload: dict,
) -> dict:
    journal, changed = _load_journal(project)

    entries = journal.get("entries", [])

    for index, current in enumerate(entries):
        if current.get("id") != entry_id:
            continue

        updated = {
            "id": entry_id,
            "date": payload["date"],
            "activity": payload["activity"],
            "location": payload.get("location"),
            "start_time": payload.get("start_time"),
            "end_time": payload.get("end_time"),
            "tags": [tag.strip().lower() for tag in payload.get("tags", []) if tag.strip()],
            "highlight": payload.get("highlight"),
            "notes": payload.get("notes"),
            "logged_at": current.get("logged_at") or datetime.now().isoformat(timespec="seconds"),
        }

        entries[index] = updated
        _save_journal(project, journal)

        if changed:
            _save_journal(project, journal)

        return updated

    raise FileNotFoundError("Journal entry not found.")


def delete_entry(
    project: VideoProject,
    entry_id: str,
) -> None:
    journal, changed = _load_journal(project)

    entries = journal.get("entries", [])
    remaining = [entry for entry in entries if entry.get("id") != entry_id]

    if len(remaining) == len(entries):
        raise FileNotFoundError("Journal entry not found.")

    journal["entries"] = remaining
    _save_journal(project, journal)

    if changed:
        _save_journal(project, journal)
