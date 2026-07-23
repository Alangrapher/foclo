# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Foclo.
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
        'app.platform_adapter', 'timer_engine',
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
    name='Foclo',
    debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, console=False,
)

app = BUNDLE(
    exe,
    name='Foclo.app',
    icon='AppIcon.icns',
    bundle_identifier='com.foclo.app',
    info_plist={
        'CFBundleName': 'Foclo',
        'CFBundleDisplayName': 'Foclo',
        'CFBundleVersion': '1.0',
        'CFBundleShortVersionString': '1.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '13.0',
    },
)
