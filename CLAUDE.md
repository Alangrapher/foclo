# Alangrapher — WebView Edition

## ⚠️ CRITICAL: Architecture Constraint (READ FIRST)

**This is NOT a CustomTkinter project.** The previous attempt with CTk failed because CTk cannot replicate CSS-level cascade, SVG rendering, and global font families.

**New approach:** Use `pywebview` to render the prototype HTML directly in a native macOS WebView (WebKit). Python handles ONLY the backend (timer engine, SQLite, system tray). The prototype HTML at `prototype.html` is the single source of truth for UI — its CSS must NOT be modified.

## Architecture

```
┌─────────────────────────────────────┐
│  pywebview (760×620)                │
│  ┌───────────────────────────────┐  │
│  │  WebKit (native macOS)       │  │
│  │  prototype.html + dynamic JS │  │
│  │  window.pywebview.api.xxx()  │  │
│  └──────────┬───────────────────┘  │
│             │ JS bridge             │
│  ┌──────────▼───────────────────┐  │
│  │  Python Backend              │  │
│  │  - api.py (JS bridge class)  │  │
│  │  - timer_engine.py           │  │
│  │  - database.py (SQLite)      │  │
│  │  - tray.py (system tray)     │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
```

## Key Rules

1. **DO NOT modify prototype.html CSS.** It already works perfectly. All Moss mode, dark mode, animations, SVG icons are correct.
2. **DO NOT use CustomTkinter or Tkinter.** The window is pywebview.
3. **DO NOT rewrite icons or SVG.** prototype.html has inline Lucide SVGs with correct stroke-width, colors, and viewBox.
4. **Add JS dynamic behavior** to prototype.html — replace static mock data with live data from Python backend.
5. **Python backend** uses TimerEngine + SQLite as specified in DECISIONS.md.
6. **JS bridge** uses `window.pywebview.api.method_name()` pattern.

## Project Files

- `main.py` — pywebview entry point, 760×620 window
- `api.py` — JS bridge API (exposed to JavaScript)
- `timer_engine.py` — Timer state machine, slot management
- `database.py` — SQLite with WAL mode, tables per DECISIONS.md
- `models.py` — Data classes for Subject, Record, Todo
- `tray.py` — macOS system tray via rumps
- `index.html` — wrapper that includes prototype.html content with JS bridge initialization
- `requirements.txt` — pywebview, rumps, pyobjc
- `prototype.html` — UNTOUCHED (source of truth)

## JS Bridge API (api.py)

The Python class `Api` exposes these methods to JavaScript:

```python
class Api:
    # Timer
    def start_slot(self, slot_index: int) -> dict
    def pause_slot(self, slot_index: int) -> dict
    def archive_slot(self, slot_index: int, subject_id: int, description: str) -> dict
    def get_slot_state(self, slot_index: int) -> dict
    def get_all_slots(self) -> list[dict]
    def get_display_time(self, slot_index: int) -> str
    def add_slot(self) -> dict
    def remove_slot(self, slot_index: int) -> dict

    # Subjects
    def get_subjects(self) -> list[dict]
    def add_subject(self, name: str, color: str) -> dict
    def update_subject(self, subject_id: int, name: str, color: str) -> dict
    def delete_subject(self, subject_id: int) -> dict

    # Records
    def get_records(self, filter: str = "today") -> list[dict]
    def add_record(self, subject_id: int, description: str, start_time: str, end_time: str) -> dict
    def update_record(self, record_id: int, **kwargs) -> dict
    def delete_record(self, record_id: int) -> dict

    # Todos
    def get_todos(self) -> list[dict]
    def add_todo(self, subject: str, description: str) -> dict
    def toggle_todo(self, todo_id: int) -> dict
    def delete_todo(self, todo_id: int) -> dict

    # Settings
    def get_settings(self) -> dict
    def update_setting(self, key: str, value: str) -> dict
```

## Dynamic HTML Changes (index.html or modified prototype.html)

The HTML needs these JS additions WITHOUT changing CSS:

1. Timer page: Replace static "00:00:00" with live `setInterval` calling `pywebview.api.get_display_time(i)`
2. Todo page: Replace static list items with dynamic rendering from `pywebview.api.get_todos()`
3. Records page: Replace static table rows with dynamic rendering from `pywebview.api.get_records(filter)`
4. Subjects page: Replace static list with dynamic rendering from `pywebview.api.get_subjects()`
5. Timer Start/Pause/Archive buttons: Call `pywebview.api.start_slot()` etc.
6. Theme toggle (Dark/Light/Moss): Keep the existing CSS class toggling logic — it's already correct CSS-only
7. Compact mode: Keep the existing JS logic — it's already correct

## Database Schema (DECISIONS.md compliant)

See DECISIONS.md for full table definitions. Key: SQLite with WAL mode, 5 tables (subjects, records, todos, settings, slot_state).

## Timer Engine (DECISIONS.md compliant)

State machine: IDLE → RUNNING → PAUSED → RUNNING (via Resume) or IDLE (via Archive). Multi-slot mutually exclusive. `time.time()` delta-based timing, no threads.

## Known Pitfalls

- pywebview on macOS uses WebKit, which is the same engine as Safari. All prototype CSS works.
- `window.pywebview.api` is only available after `pywebview` is loaded. Use `window.addEventListener('pywebviewready', ...)`.
- rumps tray icon: use a small PNG template image. Title updates from tick loop.
- SQLite WAL: `PRAGMA journal_mode=WAL` at init. Backup copies need `PRAGMA wal_checkpoint(TRUNCATE)`.
