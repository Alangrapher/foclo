# RUNBOOK — Foclo

## 环境要求

- **Python**: 3.13+
- **虚拟环境**: `/tmp/foclo_venv/`
- **依赖**: pywebview, pyobjc (macOS)
- **无 Node.js / npm 依赖**

## 依赖安装

```bash
python3 -m venv /tmp/foclo_venv
/tmp/foclo_venv/bin/pip install pywebview pyobjc
```

## 启动应用

```bash
# 终端直接启动
cd ~/Projects/Foclo
/tmp/foclo_venv/bin/python3 main.py

# 或双击
open ~/Projects/Alangrapher/launch.command
```

## 运行测试

```bash
cd ~/Projects/Foclo
/tmp/foclo_venv/bin/python3 -m pytest tests/ -v
```

## 手动冒烟测试

参见 `SMOKE_TEST.md`。

## 应用数据存储

- **数据库**: `~/Projects/Alangrapher/data/foclo.db` (SQLite, WAL 模式)
- **备份**: 未启用（后续通过 Auto Backup setting 配置）

## 技术栈

| 层 | 技术 |
|---|------|
| 渲染 | pywebview + macOS WebKit (Cocoa) |
| 前端 | 纯 HTML/CSS/JS，零框架 |
| 后端 | Python 3.13 + SQLite |
| 窗口 | frameless 760×620, pywebview Cocoa 后端 |

## 已知问题

参见 `KNOWN_ISSUES.md`。
