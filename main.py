"""Alangrapher — WebView edition.

pywebview renders prototype HTML in native WebKit.
Python handles timer engine, SQLite, and system tray.
"""
from __future__ import annotations

import os
import webview
from api import Api
from database import init_db
# from tray import Tray

# Resolve absolute path to index.html
INDEX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")


def main():
    init_db()

    api = Api()
    # tray = Tray(api)

    # Read index.html content
    with open(INDEX_PATH, "r") as f:
        html = f.read()

    window = webview.create_window(
        title="Alangrapher",
        html=html,
        width=760,
        height=620,
        frameless=True,
        resizable=False,
        js_api=api,
    )

    webview.start(gui="cocoa")


if __name__ == "__main__":
    main()
