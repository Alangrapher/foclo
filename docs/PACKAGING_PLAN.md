# PACKAGING PLAN — Alangrapher

## 当前状态

- 应用功能完整，本地开发可运行
- 未执行正式打包
- 启动方式：`python3 main.py` 或双击 `launch.command`

## 打包方案评估

| 工具 | macOS | Windows | 评价 |
|------|-------|---------|------|
| **PyInstaller** | ✅ | ✅ | 最成熟，社区大，WebView 支持好 |
| **py2app** | ✅ | ❌ | macOS 专用，但 pywebview 兼容性不如 PyInstaller |
| **Nuitka** | ✅ | ✅ | 编译型，体积小但复杂 |

### 推荐：PyInstaller

- 同时支持 macOS .app 和 Windows .exe
- pywebview 社区已验证兼容
- `--windowed` 模式不显示终端
- 资源文件通过 `--add-data` 打包

## 打包风险

| 风险 | 严重度 | 缓解 |
|------|--------|------|
| Python 3.13 兼容 | 中 | PyInstaller 6.x+ 已支持 |
| pywebview Cocoa 后端 | 低 | 已验证，macOS 10.12+ 内置 WebKit |
| Windows WebView2 | 中 | 需 Edge Runtime（Win10+ 默认安装） |
| 数据库路径 | 中 | platform_adapter.py 已就绪，打包前切换 |
| macOS 代码签名 | 高 | 需 Apple Developer 账号 + 公证，否则 Gatekeeper 拦截 |
| Windows 杀毒误报 | 中 | PyInstaller 打包的 .exe 常被误报，需提交白名单 |
| 静态 UI 文件 | 低 | `--add-data "ui:ui"` 即可 |

## 打包前待办

1. **切换数据库路径** — storage.py 使用 `platform_adapter.database_path()` 替代相对路径
2. **Windows 启动脚本** — 创建 `launch.bat`
3. **图标** — 提供 `.icns` (macOS) 和 `.ico` (Windows)
4. **版本号** — 设定正式版本号

## PyInstaller 命令参考

```bash
# macOS .app
pyinstaller --windowed --name Alangrapher \
  --add-data "ui:ui" \
  --add-data "app:app" \
  --add-data "timer_engine.py:." \
  --hidden-import webview.platforms.cocoa \
  --icon alangrapher.icns \
  main.py

# macOS .dmg (after .app built)
hdiutil create -volname Alangrapher -srcfolder dist/Alangrapher.app Alangrapher.dmg

# Windows .exe
pyinstaller --windowed --name Alangrapher \
  --add-data "ui;ui" \
  --add-data "app;app" \
  --add-data "timer_engine.py;." \
  --hidden-import webview.platforms.winforms \
  --icon alangrapher.ico \
  main.py
```

## macOS 签名与公证

```bash
# 签名
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name (TEAMID)" \
  dist/Alangrapher.app

# 公证
xcrun notarytool submit Alangrapher.dmg \
  --apple-id you@example.com --team-id TEAMID --wait

# 装订
xcrun stapler staple dist/Alangrapher.app
```

## 不推荐现在就打包

- 应用仍在调试完善中
- Export / Auto Backup 等功能尚未实现
- 建议功能完整后再执行打包
