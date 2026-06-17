"""Platform adapter — centralizes OS-specific paths and behaviors."""
from __future__ import annotations

import sys
from pathlib import Path


def app_data_dir() -> Path:
    """Return the platform-appropriate app data directory."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path.home() / "AppData" / "Local"
    else:
        base = Path.home() / ".local" / "share"
    return base / "Alangrapher"


def database_path() -> Path:
    """Return the SQLite database path."""
    return app_data_dir() / "alangrapher.db"


def export_dir() -> Path:
    """Return the default export directory."""
    return Path.home() / "Documents" / "AlangrapherExports"


def modifier_key() -> str:
    """Return the platform modifier key name for UI display."""
    return "Cmd" if sys.platform == "darwin" else "Ctrl"


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_windows() -> bool:
    return sys.platform == "win32"


def is_bundled() -> bool:
    """Return True if running as a macOS .app bundle."""
    try:
        from Foundation import NSProcessInfo
        return "YES" == NSProcessInfo.processInfo().environment().get("ALANGRAPHER_BUNDLED", "NO")
    except ImportError:
        return False
