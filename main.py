"""Alangrapher — WebView edition.

pywebview renders prototype HTML in native WebKit.
Python handles timer engine, SQLite, and system tray.
"""
from __future__ import annotations

import os
import sys
import webview
from app.bridge import Api
from app.storage import init_db
from app.backup_service import BackupService

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def _resource_path(relative_path: str) -> str:
    """Get abs path, works for dev and PyInstaller (onedir or onefile)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, relative_path)
    exe_dir = os.path.dirname(sys.executable)
    # macOS .app bundle: data files in ../Resources/
    resources = os.path.join(exe_dir, "..", "Resources", relative_path)
    if os.path.exists(resources):
        return resources
    return os.path.join(exe_dir, relative_path)


UI_DIR = _resource_path("ui")
INDEX_PATH = os.path.join(UI_DIR, "index.html")
CSS_PATH = os.path.join(UI_DIR, "styles.css")
JS_PATH = os.path.join(UI_DIR, "app.js")


def build_html() -> str:
    """Read ui/* files and inline CSS/JS into a single HTML string."""
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        css = f.read()
    with open(JS_PATH, "r", encoding="utf-8") as f:
        js = f.read()

    html = html.replace("<!-- INLINE_CSS -->", f"<style>\n{css}\n</style>")
    html = html.replace("<!-- INLINE_JS -->", f"<script>\n{js}\n</script>")
    return html


def main():
    init_db()

    backup = BackupService()
    backup.start()

    api = Api(backup_service=backup)
    html = build_html()

    window = webview.create_window(
        title="Alangrapher",
        html=html,
        width=760,
        height=620,
        frameless=True,
        resizable=False,
        js_api=api,
    )
    api.set_window(window)

    # Tray icon — macOS only (NSStatusBar + SF Symbols)
    if sys.platform == "darwin":
        from app.tray import TrayIcon
        tray = TrayIcon(window, check_fn=lambda: any(
            s.status == "running" for s in api.engine.slots
        ))
        tray.start()
        api.set_tray(tray)
    else:
        api.set_tray(None)

    webview.start(gui="cocoa" if sys.platform == "darwin" else None)

    # BUG 11: graceful shutdown — stop the backup timer to prevent
    # daemon thread from writing a corrupt half-written backup on exit
    backup.stop()


if __name__ == "__main__":
    main()
