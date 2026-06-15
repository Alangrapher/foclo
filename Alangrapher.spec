# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Alangrapher.
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
        'pywebview', 'webview', 'webview.platforms.cocoa',
        'app', 'app.bridge', 'app.storage', 'app.tray',
        'app.backup_service', 'app.export_service', 'app.record_service',
        'app.subject_service', 'app.todo_service', 'app.settings_service',
        'app.platform_adapter', 'timer_engine', 'models',
        'AppKit', 'Foundation', 'Quartz', 'objc',
    ],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'PIL', 'cv2'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    win_no_prefer_redirects=False, win_private_assemblies=False,
    cipher=None, noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='Alangrapher',
    debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, console=False,
)

app = BUNDLE(
    exe,
    name='Alangrapher.app',
    icon=None,
    bundle_identifier='com.alangrapher.app',
    info_plist={
        'CFBundleName': 'Alangrapher',
        'CFBundleDisplayName': 'Alangrapher',
        'CFBundleVersion': '0.22',
        'CFBundleShortVersionString': '0.22',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '13.0',
    },
)
