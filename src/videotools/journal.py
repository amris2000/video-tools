import json
from datetime import datetime
from pathlib import Path


def ask(prompt, default=None):
    if default:
        value = input(f"{prompt} [{default}]: ").strip()
        return value or default

    return input(f"{prompt}: ").strip()


def ask_date():
    today = datetime.now().strftime("%Y%m%d")

    while True:
        value = input(
            f"Date YYYYMMDD [{today}]: "
        ).strip()

        value = value or today

        for fmt in ("%Y%m%d", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(value, fmt)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                pass

        print(
            "Invalid date. "
            "Use YYYYMMDD, for example 20260912."
        )


def ask_time(prompt):
    while True:
        value = input(
            f"{prompt} HH:MM (e.g. 15:30, optional): "
        ).strip()

        if not value:
            return None

        try:
            parsed = datetime.strptime(value, "%H:%M")
            return parsed.strftime("%H:%M")
        except ValueError:
            print(
                "Invalid time. "
                "Use 24-hour HH:MM, for example 09:15 or 18:30."
            )


def load_journal(journal_file: Path):
    if not journal_file.exists():
        return {
            "created": datetime.now().isoformat(
                timespec="seconds"
            ),
            "entries": [],
        }

    return json.loads(
        journal_file.read_text(encoding="utf-8")
    )


def save_journal(
    journal_file: Path,
    journal: dict,
):
    journal_file.write_text(
        json.dumps(
            journal,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

def list_journal_entries(project_root: Path):
    journal_file = project_root / "journal.json"
    journal = load_journal(journal_file)

    entries = journal.get("entries", [])

    if not entries:
        print()
        print("No journal entries found.")
        return

    entries = sorted(
        entries,
        key=lambda entry: (
            entry.get("date", ""),
            entry.get("start_time") or "",
        ),
    )

    print()
    print("=" * 60)
    print("VIDEO JOURNAL")
    print("=" * 60)

    for entry in entries:
        print()

        date = entry.get("date", "Unknown date")
        activity = entry.get("activity") or "Untitled activity"

        print(f"{date} — {activity}")

        location = entry.get("location")

        if location:
            print(f"Location: {location}")

        start_time = entry.get("start_time")
        end_time = entry.get("end_time")

        if start_time or end_time:
            time_text = start_time or "?"

            if end_time:
                time_text += f"–{end_time}"

            print(f"Time:     {time_text}")

        tags = entry.get("tags", [])

        if tags:
            print(f"Tags:     {', '.join(tags)}")

        highlight = entry.get("highlight")

        if highlight:
            print(f"Highlight: {highlight}")

        notes = entry.get("notes")

        if notes:
            print(f"Notes:     {notes}")

        print("-" * 60)

def add_journal_entry(project_root: Path):
    journal_file = project_root / "journal.json"

    print()
    print("=" * 50)
    print("VIDEO JOURNAL")
    print("=" * 50)
    print()

    entry_date = ask_date()

    activity = ask("Activity")
    location = ask("Location")

    start_time = ask_time("Start time")
    end_time = ask_time("End time")

    tags_raw = ask("Tags (comma separated)")

    tags = [
        tag.strip().lower()
        for tag in tags_raw.split(",")
        if tag.strip()
    ]

    highlight = ask(
        "Best footage / highlights"
    )

    notes = ask("Notes")

    entry = {
        "date": entry_date,
        "activity": activity,
        "location": location,
        "start_time": start_time,
        "end_time": end_time,
        "tags": tags,
        "highlight": highlight or None,
        "notes": notes or None,
        "logged_at": datetime.now().isoformat(
            timespec="seconds"
        ),
    }

    journal = load_journal(journal_file)

    journal["entries"].append(entry)

    save_journal(
        journal_file,
        journal,
    )

    print()
    print("Saved ✓")
    print(journal_file)