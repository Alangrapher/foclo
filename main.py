"""Alangrapher — WebView edition.

pywebview renders prototype HTML in native WebKit.
Python handles timer engine, SQLite, and system tray.
"""
from __future__ import annotations

import os
import webview
from api import Api
from database import init_db

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(PROJECT_DIR, "ui")
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

    api = Api()
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

    webview.start(gui="cocoa")


if __name__ == "__main__":
    main()
