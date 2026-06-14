# KNOWN ISSUES — Alangrapher

## 已确认

| # | 问题 | 影响 | 状态 |
|---|------|------|------|
| 1 | pywebview `html=` 参数加载时，CSS/JS 必须内联在单个 HTML 文件中，无法使用外部 `<link>` 或 `<script src>` | 前端文件拆分需要 Python 端做构建拼接 | 待解决 |
| 2 | `webview.start(gui="cocoa")` 硬编码 macOS 后端 | 跨平台需适配 | 待重构 |
| 3 | 系统托盘（tray.py）未启用 | 关闭窗口时应用完全退出 | 低优先级 |
| 4 | Auto Backup 开关无实际后端逻辑 | 功能占位 | 低优先级 |
| 5 | Export 按钮仅更新时间戳，无实际导出 | 功能占位 | 低优先级 |
| 6 | 数据库路径硬编码在 database.py | 跨平台需适配 | 待重构 |

## 已在本次重构中解决

| # | 问题 | 解决方案 |
|---|------|----------|
| — | api.py 混合所有业务逻辑 (245行) | Stage 3 拆分为 bridge + service 模块 |
| — | index.html 单文件 1262行 | Stage 2 拆分为 ui/ 目录 |
| — | 无测试 | Stage 5 添加 tests/ |
| — | 无文档 | Stage 1 添加 docs/ |

## 跨平台注意事项

- macOS `.command` 启动脚本在 Windows 上不可用，需提供 `.bat` 替代
- pywebview Windows 后端使用 Edge WebView2，需确保系统已安装
- macOS `pyobjc` 依赖在 Windows 上不需要
