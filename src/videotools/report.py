
from html import escape
from pathlib import Path

def format_duration(seconds: float) -> str:
    total_seconds = int(round(seconds))

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    return f"{minutes:02}:{seconds:02}"


def generate_html_report(
    report: dict,
    output_file: Path,
    journal: dict | None = None,
):
    clips = report["clips"]
    summary = report["summary"]

    grouped = {}

    for clip in clips:
        relative_path = Path(clip["relative_path"])

        parts = relative_path.parts

        date_folder = "Unknown"

        if len(parts) >= 3:
            date_folder = parts[1]

        grouped.setdefault(date_folder, []).append(clip)

    sections = []

    journal = journal or {"entries": []}

    journal_by_date = {}

    for entry in journal.get("entries", []):
        date_value = entry.get("date")

        if not date_value:
            continue

        # 2026-09-06 -> 20260906
        date_key = date_value.replace("-", "")

        journal_by_date.setdefault(
            date_key,
            [],
        ).append(entry)

    for date_folder, date_clips in sorted(grouped.items()):
        day_journal_entries = journal_by_date.get(
            date_folder,
            [],
        )

        journal_cards = []

        for entry in day_journal_entries:
            activity = escape(
                entry.get("activity") or "Untitled activity"
            )

            location = escape(
                entry.get("location") or ""
            )

            start_time = entry.get("start_time")
            end_time = entry.get("end_time")

            time_text = ""

            if start_time and end_time:
                time_text = f"{start_time}–{end_time}"
            elif start_time:
                time_text = start_time

            tags = entry.get("tags", [])

            tags_html = "".join(
                f'<span class="tag">{escape(tag)}</span>'
                for tag in tags
            )

            highlight = escape(
                entry.get("highlight") or ""
            )

            notes = escape(
                entry.get("notes") or ""
            )

            journal_cards.append(
                f"""
                <div class="journal-card">
                    <div class="journal-heading">
                        <h3>{activity}</h3>
                        <span class="journal-time">
                            {escape(time_text)}
                        </span>
                    </div>

                    {
                        f'<div class="journal-location">{location}</div>'
                        if location
                        else ''
                    }

                    {
                        f'<div class="tags">{tags_html}</div>'
                        if tags
                        else ''
                    }

                    {
                        f'''
                        <div class="journal-highlight">
                            <strong>Highlight:</strong>
                            {highlight}
                        </div>
                        '''
                        if highlight
                        else ''
                    }

                    {
                        f'''
                        <div class="journal-notes">
                            {notes}
                        </div>
                        '''
                        if notes
                        else ''
                    }
                </div>
                """
            )

        journal_html = ""

        if journal_cards:
            journal_html = f"""
            <div class="journal-section">
                {''.join(journal_cards)}
            </div>
            """

        cards = []

        for clip in date_clips:
            video = clip["video"]
            audio = clip.get("audio")

            fps = video["fps"]

            high_frame_rate = fps >= 60

            badge = ""

            if high_frame_rate:
                badge = """
                <span class="badge">HIGH FRAME RATE</span>
                """

            creation_time = (
                clip.get("creation_time_local")
                or clip.get("creation_time")
                or "Unknown"
            )

            thumbnail = clip.get("thumbnail")

            thumbnail_html = ""

            if thumbnail:
                thumbnail_relative = Path(
                    thumbnail
                ).relative_to("metadata")

                thumbnail_html = f"""
                <img
                    class="clip-thumbnail"
                    src="{escape(thumbnail_relative.as_posix())}"
                    alt="{escape(clip["name"])}"
                    loading="lazy"
                >
                """

            audio_text = "No audio"

            if audio:
                audio_text = (
                    f'{audio.get("codec", "?").upper()} · '
                    f'{audio.get("sample_rate", "?")} Hz · '
                    f'{audio.get("channels", "?")} ch'
                )

            matched_entry = clip.get("journal")

            journal_match_html = ""

            if matched_entry:
                journal_match_html = f"""
                <div class="clip-journal">
                    <strong>
                        {escape(
                            matched_entry.get("activity")
                            or "Journal activity"
                        )}
                    </strong>

                    <div>
                        {escape(
                            matched_entry.get("location")
                            or ""
                        )}
                    </div>
                </div>
                """

            cards.append(
                f"""
                <article class="clip-card">
                    {thumbnail_html}
                    <div class="clip-header">
                        <div>
                            <h3>{escape(clip["name"])}</h3>
                            <div class="path">
                                {escape(clip["relative_path"])}
                            </div>
                        </div>

                        {badge}
                    </div>

                    <div class="stats">
                        <div>
                            <span class="label">Duration</span>
                            <span>
                                {format_duration(clip["duration"])}
                            </span>
                        </div>

                        <div>
                            <span class="label">Resolution</span>
                            <span>
                                {video["width"]} × {video["height"]}
                            </span>
                        </div>

                        <div>
                            <span class="label">Frame rate</span>
                            <span>
                                {fps} fps
                            </span>
                        </div>

                        <div>
                            <span class="label">Codec</span>
                            <span>
                                {escape(str(video["codec"]).upper())}
                            </span>
                        </div>
                    </div>
                    {journal_match_html}
                    <div class="details">
                        <div>
                            <strong>Created:</strong>
                            {escape(creation_time)}
                        </div>

                        <div>
                            <strong>Audio:</strong>
                            {escape(audio_text)}
                        </div>

                        <div>
                            <strong>Pixel format:</strong>
                            {escape(str(video.get("pixel_format")))}
                        </div>
                    </div>
                </article>
                """
            )

        sections.append(
            f"""
            <section class="day-section">
                <h2>{escape(date_folder)}</h2>

                {journal_html}

                <div class="clip-grid">
                    {''.join(cards)}
                </div>
            </section>
            """
        )

    format_rows = []

    for group in summary.get("formats", []):
        format_rows.append(
            f"""
            <tr>
                <td>{group["count"]}</td>
                <td>{group["width"]} × {group["height"]}</td>
                <td>{group["fps"]} fps</td>
            </tr>
            """
        )

    warnings_html = ""

    warnings = summary.get("warnings", [])

    if warnings:
        warning_items = "".join(
            f"<li>{escape(warning['message'])}</li>"
            for warning in warnings
        )

        warnings_html = f"""
        <section class="warnings">
            <h2>Warnings</h2>
            <ul>
                {warning_items}
            </ul>
        </section>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>Clip Report</title>

    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            font-family:
                system-ui,
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;
            background: #f4f5f7;
            color: #1f2937;
        }}

        .container {{
            width: min(1200px, 92%);
            margin: 0 auto;
            padding: 40px 0 80px;
        }}

        header {{
            margin-bottom: 32px;
        }}

        h1 {{
            margin: 0 0 8px;
            font-size: 2.2rem;
        }}

        .subtitle {{
            color: #6b7280;
        }}

        .clip-thumbnail {{
            display: block;
            width: 100%;
            aspect-ratio: 16 / 9;
            object-fit: cover;
            border-radius: 10px;
            margin-bottom: 16px;
            background: #e5e7eb;
        }}

        .summary {{
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin: 28px 0;
        }}

        .summary-card {{
            background: white;
            border-radius: 12px;
            padding: 18px;
            box-shadow:
                0 1px 3px rgba(0, 0, 0, 0.08);
        }}

        .summary-card .label {{
            display: block;
            color: #6b7280;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 6px;
        }}

        .summary-card .value {{
            font-size: 1.3rem;
            font-weight: 700;
        }}



        .format-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow:
                0 1px 3px rgba(0, 0, 0, 0.08);
        }}

        .format-table th,
        .format-table td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }}

        .format-table th {{
            background: #f9fafb;
        }}

        .warnings {{
            margin: 28px 0;
            padding: 18px 22px;
            background: #fff7ed;
            border-left: 4px solid #f97316;
            border-radius: 8px;
        }}

        .warnings h2 {{
            margin-top: 0;
        }}

        .day-section {{
            margin-top: 42px;
        }}

        .day-section h2 {{
            margin-bottom: 16px;
            font-size: 1.5rem;
        }}

        .clip-grid {{
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(320px, 1fr));
            gap: 18px;
        }}

        .clip-card {{
            background: white;
            border-radius: 14px;
            padding: 20px;
            box-shadow:
                0 2px 8px rgba(0, 0, 0, 0.07);
        }}

        .clip-header {{
            display: flex;
            justify-content: space-between;
            gap: 16px;
            align-items: flex-start;
        }}

        .clip-header h3 {{
            margin: 0 0 4px;
            font-size: 1.05rem;
        }}

        .clip-journal {{
            margin-top: 14px;
            padding: 10px 12px;
            background: #eef2ff;
            border-radius: 8px;
            font-size: 0.85rem;
            color: #3730a3;
        }}

        .path {{
            color: #6b7280;
            font-size: 0.8rem;
            word-break: break-all;
        }}

        .badge {{
            flex-shrink: 0;
            background: #111827;
            color: white;
            font-size: 0.7rem;
            font-weight: 700;
            padding: 6px 8px;
            border-radius: 999px;
            letter-spacing: 0.04em;
        }}

        .stats {{
            display: grid;
            grid-template-columns:
                repeat(2, minmax(0, 1fr));
            gap: 12px;
            margin-top: 18px;
        }}

        .stats > div {{
            padding: 10px;
            background: #f9fafb;
            border-radius: 8px;
        }}

        .stats .label {{
            display: block;
            color: #6b7280;
            font-size: 0.75rem;
            margin-bottom: 3px;
        }}

        .details {{
            margin-top: 16px;
            color: #4b5563;
            font-size: 0.88rem;
            line-height: 1.6;
        }}

        .journal-section {{
            margin-bottom: 20px;
        }}

        .journal-card {{
            background: #eef2ff;
            border-left: 4px solid #6366f1;
            border-radius: 10px;
            padding: 18px 20px;
            margin-bottom: 14px;
        }}

        .journal-heading {{
            display: flex;
            justify-content: space-between;
            gap: 16px;
            align-items: baseline;
        }}

        .journal-heading h3 {{
            margin: 0;
        }}

        .journal-time {{
            color: #4f46e5;
            font-weight: 600;
            white-space: nowrap;
        }}

        .journal-location {{
            margin-top: 4px;
            color: #6b7280;
        }}

        .tags {{
            margin-top: 12px;
        }}

        .tag {{
            display: inline-block;
            background: white;
            border-radius: 999px;
            padding: 4px 9px;
            margin-right: 6px;
            margin-bottom: 4px;
            font-size: 0.78rem;
        }}

        .journal-highlight {{
            margin-top: 12px;
        }}

        .journal-notes {{
            margin-top: 8px;
            color: #4b5563;
        }}
        
        @media (max-width: 600px) {{
            .container {{
                width: 94%;
                padding-top: 24px;
            }}

            .stats {{
                grid-template-columns: 1fr;
            }}

            .clip-header {{
                flex-direction: column;
            }}
        }}
    </style>
</head>

<body>
    <div class="container">

        <header>
            <h1>Clip Report</h1>
            <div class="subtitle">
                Generated by video-tools
            </div>
        </header>

        <section class="summary">
            <div class="summary-card">
                <span class="label">Clips</span>
                <span class="value">
                    {summary["clip_count"]}
                </span>
            </div>

            <div class="summary-card">
                <span class="label">Total duration</span>
                <span class="value">
                    {format_duration(
                        summary["total_duration_seconds"]
                    )}
                </span>
            </div>

            <div class="summary-card">
                <span class="label">Resolution</span>
                <span class="value">
                    {summary["recommended_width"]}
                    ×
                    {summary["recommended_height"]}
                </span>
            </div>

            <div class="summary-card">
                <span class="label">Default FPS</span>
                <span class="value">
                    {summary["recommended_fps"]}
                </span>
            </div>
        </section>

        <section>
            <h2>Formats</h2>

            <table class="format-table">
                <thead>
                    <tr>
                        <th>Clips</th>
                        <th>Resolution</th>
                        <th>Frame rate</th>
                    </tr>
                </thead>

                <tbody>
                    {''.join(format_rows)}
                </tbody>
            </table>
        </section>

        {warnings_html}

        {''.join(sections)}

    </div>
</body>
</html>
"""

    output_file.write_text(
        html,
        encoding="utf-8",
    )