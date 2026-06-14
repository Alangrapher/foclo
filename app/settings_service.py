"""Settings service."""
from __future__ import annotations

from app.storage import get_setting, update_setting as _update


def get_settings() -> dict:
    return {
        "default_slots": get_setting("default_slots", "3"),
        "week_starts_on": get_setting("week_starts_on", "Monday"),
        "compact_by_default": get_setting("compact_by_default", "0"),
        "auto_backup": get_setting("auto_backup", "1"),
        "backup_location": get_setting("backup_location", ""),
        "minimize_to_tray": get_setting("minimize_to_tray", "1"),
    }


def update_setting(key: str, value: str) -> dict:
    _update(key, value)
    return {"ok": True}
