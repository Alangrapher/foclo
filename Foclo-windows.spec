# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Foclo — Windows (EXE only, no BUNDLE).
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

a = Analysis(
    ['main.py'],
    pathex=[SPECPATH],
    binaries=[],
    datas=[
        ('ui/index.html', 'ui'),
        ('ui/styles.css', 'ui'),
        ('ui/app.js', 'ui'),
    ],
    hiddenimports=[
        'pywebview', 'webview',
        'app', 'app.bridge', 'app.storage', 'app.tray_windows',
        'app.backup_service', 'app.export_service', 'app.record_service',
        'app.subject_service', 'app.todo_service', 'app.settings_service',
        'app.platform_adapter', 'timer_engine',
        'PIL', 'PIL.Image', 'PIL.ImageDraw',
    ],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'cv2'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    win_no_prefer_redirects=False, win_private_assemblies=False,
    cipher=None, noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='Foclo',
    debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, console=False,
    icon='AppIcon.ico',
)
