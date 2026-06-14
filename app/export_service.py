"""Export timesheet to Excel (matching the weekly template format).

Template columns:
  A: Project No.
  B: Project name (Subject.name)
  C: Descriptions (aggregated itemised list)
  D: Hour(s) - Weekly  (=SUM formula)
  E: Days (Sunday – Friday, + Saturday if any Saturday records exist)
  F: Hour(s) - Daily

Each subject gets a block: header row + 6 day rows (7 if Saturday present).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from collections import defaultdict

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill


ALL_DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
DAY_ABBR = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def _week_range(ref_date: date | None = None) -> tuple[date, date]:
    """Return (sunday, saturday) bounding the week containing ref_date."""
    d = ref_date or date.today()
    sunday = d - timedelta(days=(d.weekday() + 1) % 7)
    if sunday > d:
        sunday -= timedelta(days=7)
    saturday = sunday + timedelta(days=6)
    return sunday, saturday


def export_timesheet(
    output_path: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> str:
    """Export records for a date range to the template format. Returns path.

    If no dates given, defaults to current week (Sunday–Saturday).
    """
    from app.storage import get_conn
    from app.subject_service import get_subjects

    sweek, eweek = _week_range(start_date)
    # Use explicit range if provided, otherwise default week
    s = start_date if start_date else sweek
    e = end_date if end_date else (start_date if start_date else eweek)

    # Fetch records in the week
    conn = get_conn()
    rows = conn.execute(
        """SELECT r.id, r.subject_id, r.description, r.start_time, r.duration_s,
                  s.name AS subject_name
           FROM records r
           LEFT JOIN subjects s ON r.subject_id = s.id
           WHERE date(r.start_time) BETWEEN ? AND ?
           ORDER BY r.subject_id, r.start_time""",
        (s.isoformat(), e.isoformat()),
    ).fetchall()
    conn.close()

    if not rows:
        raise ValueError(f"No records found for {s} – {e}")

    # Group by subject_id, aggregate by day (always 7-day internal)
    subject_groups: dict[int, list] = defaultdict(list)
    for r in rows:
        subject_groups[r["subject_id"] or 0].append(r)

    subjects = get_subjects()
    subject_map = {s["id"]: s for s in subjects}
    # Also include archived subjects that have records
    conn2 = get_conn()
    archived_rows = conn2.execute(
        "SELECT id, name FROM subjects WHERE archived = 1 AND id IN ("
        "SELECT DISTINCT subject_id FROM records WHERE subject_id IS NOT NULL)"
    ).fetchall()
    conn2.close()
    for r in archived_rows:
        if r["id"] not in subject_map:
            subject_map[r["id"]] = dict(r)
    ordered_ids = list(subject_groups.keys())
    for s in subjects:
        if s["id"] not in ordered_ids:
            ordered_ids.append(s["id"])

    # First pass: aggregate all days, detect Saturday usage
    all_day_hours: dict[int, dict[int, float]] = {}  # sid → day_idx → hours
    all_descriptions: dict[int, list[str]] = {}
    has_saturday = False

    for sid in ordered_ids:
        recs = subject_groups.get(sid, [])
        day_hours: dict[int, float] = {i: 0.0 for i in range(7)}
        # Deduplicate descriptions: same text → merge, accumulate duration
        desc_hours: dict[str, float] = {}  # description → total hours

        for r in recs:
            dt_str = r["start_time"]
            dt = datetime.fromisoformat(dt_str) if isinstance(dt_str, str) else dt_str
            day_idx = (dt.weekday() + 1) % 7  # 0=Sun … 6=Sat
            hours = (r["duration_s"] or 0) / 3600.0
            day_hours[day_idx] += hours

            if day_idx == 6:  # Saturday
                has_saturday = True

            desc = (r["description"] or "").strip()
            if desc:
                desc_hours[desc] = desc_hours.get(desc, 0) + hours

        # Build itemised description list: "1. text (X.Xh)"
        descriptions: list[str] = []
        for i, (desc, hrs) in enumerate(desc_hours.items(), 1):
            descriptions.append(f"{i}. {desc} ({hrs:.1f}h)")

        all_day_hours[sid] = day_hours
        all_descriptions[sid] = descriptions

    # Determine output days and anchor date for YYYYMMDD labels
    num_days = 7 if has_saturday else 6
    # Anchor Sunday: the Sunday of the week containing start_date (or today)
    anchor_ref = start_date if start_date else date.today()
    anchor_sunday = anchor_ref - timedelta(days=(anchor_ref.weekday() + 1) % 7)
    if anchor_sunday > anchor_ref:
        anchor_sunday -= timedelta(days=7)
    day_labels = [
        f"{DAY_ABBR[i]} {anchor_sunday + timedelta(days=i):%Y%m%d}"
        for i in range(num_days)
    ]

    wb = Workbook()
    ws = wb.active
    # Sheet title: Excel limits to 31 chars, no [ ] : * ? / \\ 
    sheet_name = "Timesheet"
    ws.title = sheet_name

    # -- Styles --
    header_font = Font(name="Calibri", bold=True, size=11)
    header_fill = PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    # -- Column widths --
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 32
    ws.column_dimensions["C"].width = 50
    ws.column_dimensions["D"].width = 16
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 16

    # -- Header row --
    headers = ["Project No.", "Project", "Descriptions (if any)",
               "Hour(s) - Weekly", "Days", "Hour(s) - Daily"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # -- Data rows --
    row = 2
    project_no = 0

    for sid in ordered_ids:
        project_no += 1
        name = subject_map.get(sid, {}).get("name", f"Subject {sid}") if sid else "Uncategorised"
        day_hours = all_day_hours[sid]
        desc_text = "\n".join(all_descriptions.get(sid, []))

        # SUM range: project header row (Sunday) through last day
        day_row_start = row
        day_row_end = row + num_days - 1

        # Project header row (merged with Sunday)
        ws.cell(row=row, column=1, value=project_no).border = thin_border
        ws.cell(row=row, column=2, value=name).border = thin_border
        desc_cell = ws.cell(row=row, column=3, value=desc_text)
        desc_cell.border = thin_border
        desc_cell.alignment = Alignment(wrap_text=True, vertical="top")

        formula_cell = ws.cell(
            row=row, column=4,
            value=f"=SUM(F{day_row_start}:F{day_row_end})",
        )
        formula_cell.border = thin_border
        formula_cell.alignment = Alignment(horizontal="center", vertical="center")
        formula_cell.number_format = "0.0"

        # Day 0 (Sunday, same row as project header)
        ws.cell(row=row, column=5, value=day_labels[0]).border = thin_border
        ws.cell(row=row, column=5).alignment = Alignment(horizontal="center", vertical="center")
        hrs_cell = ws.cell(row=row, column=6, value=round(day_hours[0], 2))
        hrs_cell.border = thin_border
        hrs_cell.alignment = Alignment(horizontal="center", vertical="center")
        hrs_cell.number_format = "0.0"

        # Day 1 through last day
        for day_idx in range(1, num_days):
            r_num = row + day_idx
            for col in (1, 2, 3, 4):
                ws.cell(row=r_num, column=col).border = thin_border
            ws.cell(row=r_num, column=5, value=day_labels[day_idx]).border = thin_border
            ws.cell(row=r_num, column=5).alignment = Alignment(horizontal="center", vertical="center")
            h_cell = ws.cell(row=r_num, column=6, value=round(day_hours[day_idx], 2))
            h_cell.border = thin_border
            h_cell.alignment = Alignment(horizontal="center", vertical="center")
            h_cell.number_format = "0.0"

        row = row + num_days

    wb.save(output_path)
    return output_path
