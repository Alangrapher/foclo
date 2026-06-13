# Alangrapher · 技术决策

> **作用**：记录"为什么这么做"，避免未来重复讨论已决定的架构问题。
> **和 SPEC.md 的区别**：SPEC 管 UI 要做成什么样，DECISIONS 管技术为什么这么选。
> **更新规则**：每做一个技术决策实时写入。标注日期。

---

## 技术栈

| 决策 | 选项 | 选定 | 理由 |
|------|------|------|------|
| GUI 框架 | CustomTkinter vs PySide6 vs Tkinter | **CustomTkinter** ✅ | 原项目基线，迁移成本最低。Windows/macOS 双平台兼容。PySide6 更成熟但引入 Qt 依赖太重（~200MB），对 760×620 的小窗口不值。 |
| 数据库 | SQLite | ✅ | 纯本地、零配置、单文件、崩溃安全（WAL 模式）。无需安装任何服务。 |
| 打包 | PyInstaller | ✅ | macOS `.app` bundle + Windows `.exe` 同一套配置。 |
| Python 版本 | 3.13 | ✅ | venv 已配。CTk 5.2+ 兼容。 |
| 定时器引擎 | `time.time()` 增量 vs `threading.Timer` 轮询 | **`time.time()` 增量** ✅ | 不依赖线程频率。开始计时时记录 `start_time`，显示值 = `now - start_time + saved_elapsed`。`after()` 刷新 UI，不阻塞。 |
| 导出：Excel | openpyxl | ✅ | 纯 Python，无系统依赖，跨平台。 |
| 导出：Markdown | 内置 `str` 拼接 | ✅ | 零依赖。 |
| 导出：JSON | `json` 标准库 | ✅ | 零依赖。 |

---

## 数据模型（SQLite）

### 表结构

```sql
-- 主题/科目
CREATE TABLE subjects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    color       TEXT NOT NULL DEFAULT '#5E6AD2',  -- hex
    archived    INTEGER NOT NULL DEFAULT 0,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 计时记录
CREATE TABLE records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id  INTEGER REFERENCES subjects(id),
    description TEXT DEFAULT '',
    start_time  TEXT NOT NULL,              -- ISO 8601
    end_time    TEXT,                       -- NULL = 仍在计时
    duration_s  INTEGER NOT NULL DEFAULT 0, -- 秒
    slot_index  INTEGER NOT NULL DEFAULT 0, -- 哪个 slot 产生的
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 待办事项
CREATE TABLE todos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id  INTEGER REFERENCES subjects(id),
    description TEXT DEFAULT '',
    est_minutes INTEGER DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending | done | archived
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 设置 (key-value)
CREATE TABLE settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);

-- Slot 状态（崩溃恢复）
CREATE TABLE slot_state (
    slot_index  INTEGER PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'idle',  -- idle | running | paused
    subject_id  INTEGER REFERENCES subjects(id),
    description TEXT DEFAULT '',
    elapsed_s   INTEGER NOT NULL DEFAULT 0,
    started_at  TEXT
);
```

### 关键设计选择

| 决策 | 理由 |
|------|------|
| duration 存秒（INTEGER） | 避免浮点误差。显示时格式化为 `Hh Mm` 或 `HH:MM:SS`。 |
| start_time/end_time 存 ISO 8601 字符串 | SQLite 无原生 datetime，字符串可直接比较、人可读。 |
| slot_state 独立表 | 崩溃恢复不需要解析 records 表（records 的 end_time=NULL 不可靠）。slot_state 存运行时状态，程序启动即恢复。 |
| settings 用 key-value | 灵活扩展，不需要改 schema。 |
| 不用 ORM | 5 张表，手写 SQL 更轻、无黑盒。`sqlite3` 标准库够用。 |
| WAL 模式 | 读写并发不阻塞，崩溃恢复更安全。`PRAGMA journal_mode=WAL;` |

---

## 定时器引擎

```
状态机：每个 slot 独立状态
  IDLE ──Start──▶ RUNNING ──Pause──▶ PAUSED
    ▲                 │                  │
    │                 │                  ├──Resume──▶ RUNNING
    │                 │                  │
    └──Archive────────┴──Archive─────────┘
```

| 决策 | 理由 |
|------|------|
| 多 Slot 互斥 | 同一时间只有一个 slot 可以处于 RUNNING。启动新 slot → 自动 Pause 当前 running slot。 |
| 时间追踪：`start_time` + `saved_elapsed` | 无后台线程。`after(200ms)` 刷新显示。Pause 时 `saved_elapsed += now - start_time`，Resume 时重设 `start_time`。 |
| 精确度 | `time.time()` 秒级。不追求毫秒——这是时间追踪工具，不是秒表。 |
| Archive 行为 | 写一条 records（end_time=now, duration_s=elapsed），重置 slot 为 IDLE。 |
| 崩溃恢复 | 启动时读 `slot_state` 表。如果有 RUNNING 状态且 `started_at` 距今 < 24h → 恢复为 PAUSED（保守策略，防止关机期间虚增计时）。 |

---

## UI 架构

### 页面组织

```
main.py              → CTk() 实例，窗口 760×620
app.py               → 布局根：sidebar + page_container
pages/
  timer.py           → 多 slot 卡片 + 统计 tiles + 今日记录
  todo.py            → inline 输入 + 待办列表
  records.py         → 筛选 + 表格 + inline 编辑
  subjects.py        → 色块 + 名称列表 + inline 编辑
  export.py          → 日期范围 + 格式选择 + 导出
  settings.py        → toggle/select/button 配置项
widgets/
  sidebar.py         → 导航 + dark/light 切换 + Code of Timing 彩蛋
  timer_card.py      → 单 slot：时钟 + subject 下拉 + desc + 按钮
  compact_panel.py   → 浮动紧凑面板（220px）
  badge.py           → 状态标签（idle/running/paused）
  modal.py           → Code of Timing 弹窗
```

| 决策 | 理由 |
|------|------|
| 每个页面一个文件 | 原型 671 行单文件是因为 HTML 方便迭代。Python 必须拆分，否则不可维护。 |
| `after(200ms)` 刷新时钟 | CTk 是单线程事件循环。短间隔刷新不会卡 UI。 |
| 页面切换 = `pack_forget()` / `pack()` | 不是真正的路由，6 个页面全加载但只显示一个。状态保持在内存中。 |
| 原型对齐 | 每个 widget 的颜色、字号、间距从原型 CSS 变量映射到 CTk 参数。不一致的地方改代码，不改原型。 |

---

## 图标系统

| 决策 | 理由 |
|------|------|
| SVG → PIL 4x 超采样 → `ImageTk.PhotoImage` | **2026-06-13 修订**：① cairosvg 依赖 cairo 系统库，macOS brew install 挂死，不可行；② CTkImage 在 Python 3.13 有 GC bug（"pyimage" does not exist），随机崩溃。改为 PIL `ImageDraw` 直接解析 SVG XML + 4× 超采样 + LANCZOS 缩放到目标尺寸 → `ImageTk.PhotoImage`，模块级 `_PHOTO_CACHE` 字典防 GC。零系统依赖，纯 Python。 |
| 图标来源：prototype.html 内联 SVG → SPEC §9-A Lucide 映射 | **2026-06-13 新增**：原型 HTML 每个导航项使用内联 SVG（`viewBox="0 0 24 24"`，2px stroke）。SPEC §9-A 将其映射为标准 Lucide icon 名称。从 unpkg CDN 下载对应 SVG 文件到 `lucide_svgs/`。**代码中的 `_NAV_ITEMS` 必须与 SPEC §9-A 一致，不能自造名称。** |
| 图标名称映射表（SPEC §9-A → Lucide filename） | Timer=`timer`、Todo=`list-todo`、Records=`scroll-text`、Subjects=`swatch-book`、Export=`folder-input`、Settings=`hexagon`（因 `lucide-bolt` 为闪电，原型用六角形+内圆 → 回退到内联 SVG 或自定义；当前方案：直接用原型 HTML 中的 SVG path 数据作为 fallback）。 |
| 两套尺寸 | 导航 18px / 按钮 14px。Compact 面板 12px、1.2px 描边。 |
| 颜色注入：PIL `ImageDraw` 阶段 | SVG stroke 色在 PIL 渲染时通过 `fill=` 参数注入。Dark/Light/Moss 切换时重建 PhotoImage。 |

---

## 深色模式 & Moss 彩蛋

| 决策 | 理由 |
|------|------|
| `CTk.set_appearance_mode("dark"/"light")` | CTk 内置，比 CSS 变量手动映射更稳。切换时刷新图标颜色。 |
| 系统主题监听 | `darkdetect` 包（`pip install darkdetect`）→ 回调自动切换。macOS/Windows 通用。 |
| Moss 模式：手动覆盖 + 部分 moss.json | **2026-06-13 修订**：CTk 主题 JSON 只能定义标准 widget 颜色，以下需手动处理（在 `refresh_theme()` 中统一执行）：① 侧边栏 + card 左侧 3px `#cc2200` 红条——用 3px `CTkFrame` 贴边；② JetBrains Mono 全局——逐个 widget 设 `font=`（原型 `html.moss` 级联所有子元素，Python 无等效机制）；③ 顶栏 `MOSS_SYS :: ONLINE`——sidebar brand label；④ 导航 active 状态：`#f0e0d8` 底 + 左边 2px 红条 + 特殊圆角。**呼出方式同原型：Dark/Light 按钮 2 秒内连击 8 次。** |
| 窗口: `CTk()` 不搞真透明 | macOS 模糊窗口需要 `NSVisualEffectView` → pyobjc 桥接。优先级低，先做不透明底色。 |

---

## 系统托盘 & 全局快捷键

| 决策 | 理由 |
|------|------|
| macOS 托盘：`rumps` | 纯 Python 菜单栏 app。比 `pystray` 更原生。 |
| Windows 托盘：`pystray` | rumps 是 macOS-only。导入时条件判断。 |
| 全局快捷键：`pynput` | 监听全局键盘事件。Start/Pause/Archive 映射（如 Ctrl+Shift+S / P / A）。 |
| Close → 隐藏到托盘 | Settings 里的 "Minimize to tray" toggle 控制行为。默认开启。 |

---

## 备份系统

| 决策 | 理由 |
|------|------|
| 策略：定时复制 SQLite 文件 | 简单可靠。不比在线备份慢（SQLite 文件通常 < 10MB）。 |
| 频率：每小时（默认） | Settings 可改为其他间隔。 |
| 保留策略：最近 24 个备份 | 超出自动删旧。可配。 |
| 路径：`~/Documents/Alangrapher/backups/` | macOS 标准 Documents 目录。Windows 对应 `%USERPROFILE%\Documents\`。 |
| 实现：`threading.Timer` + `shutil.copy2` | 独立线程，不阻塞 UI。 |

---

## Windows 移植清单

| 关注点 | macOS | Windows | 影响 |
|--------|-------|---------|------|
| 字体 | HarmonyOS Sans SC | Microsoft YaHei | 字体 fallback 链：`'HarmonyOS Sans SC', 'Microsoft YaHei', sans-serif` |
| 计时字体 | JetBrains Mono | JetBrains Mono | 打包时携带字体文件 |
| 托盘 | `rumps` | `pystray` | 条件导入 |
| 文件路径 | `~/Documents/...` | `%USERPROFILE%\Documents\...` | `pathlib.Path.home()` 自动处理 |
| 快捷键修饰键 | `Command` | `Control` | `pynput` 区分平台 |
| 打包 | `pyinstaller --windowed` | `pyinstaller --windowed` | 同一命令 |
| 深色模式监听 | `darkdetect` | `darkdetect` | 同一包 |
| 窗口圆角/阴影 | 原生 | 原生 | CTk 统一 |

**移植策略**：不在 macOS 开发阶段为 Windows 写条件分支。MVP 完成后，单开一个 Windows 适配 sprint。

---

## 已知坑（持续更新）

| 坑 | 处理 |
|------|------|
| **CTk macOS 滚轮灵敏度** | CTk 在 macOS 的 trackpad 滚动可能过快。用 `<MouseWheel>` 事件手动限速。参考 `customtkinter-macos` skill。 |
| **CTk macOS 字体渲染** | 部分字体在 CTk 渲染模糊 → 指定 `font=CTkFont(family="...", size=...)` 而非字符串。 |
| **SVG → CTkImage 颜色注入** | `currentColor` 的 SVG 转 PNG 时需指定颜色参数。预渲染脚本要传 `--color`。 |
| **PyInstaller macOS 签名** | `.app` 需要 `codesign` 才能分发。先用 `--codesign-identity "-"` 做 ad-hoc 签名。 |
| **SQLite 文件锁** | WAL 模式下备份需先 `PRAGMA wal_checkpoint(TRUNCATE)` 确保一致性。 |
| 打包后字体路径 | PyInstaller `--add-data` 把字体打包进 bundle。运行时用 `sys._MEIPASS` 找路径。 |
| Moss 主题的部分覆盖 | CTk 主题 JSON 只能定义标准 widget 颜色。**左侧 3px 红条**（sidebar、card）需要手动创建 3px 宽的 `CTkFrame` 贴在左侧；**JetBrains Mono 全局**需逐个 widget 设 `font=`；**顶栏 `MOSS_SYS :: ONLINE`** 是自定义 label。这些不经过主题 JSON，在 Moss 切换回调里手动执行。 |

---

## 开发工作流

| 决策 | 理由 |
|------|------|
| Spec 驱动开发 | `SPEC.md` = UI 真相源。`DECISIONS.md` = 技术真相源。新功能先写 spec，再写代码。 |
| 关卡审核制 | 每个 milestone（页面完成、引擎完成）暂停等 review，不闷头全做完。 |
| 原型优先 | 任何 UI 改动先在 `prototype.html` 验证，确认后对齐到 CTk。不直接改 Python。 |

---

## 更新日志

| 日期 | 变更 |
|------|------|
| 2026-06-12 | 初始：技术栈、设计系统、开发工具、macOS 适配、已知坑 |
| 2026-06-13 22:00 | 大幅扩充：数据模型 5 表、定时器状态机、UI 架构拆分、图标预渲染、深色模式方案、托盘/快捷键、备份系统、Windows 移植清单、开发工作流 |
| 2026-06-13 22:10 | Moss 模式确认进入 Python 端——通过 `moss.json` 自定义主题 + 手动覆盖（左侧红条/字体/顶栏），保留 8 连击呼出 |
| 2026-06-13 22:20 | **图标系统修订**：① SVG 渲染路线改为 PIL 4×超采样→PhotoImage（cairo 不可用+CTkImage GC bug）；② 导航图标名对齐 SPEC §9-A（timer/list-todo/scroll-text/swatch-book/hexagon）；③ 已下载正确 Lucide SVG 到 `lucide_svgs/`；④ Moss 模式视觉对齐：侧边栏 3px 红条 + card 红条 + JetBrains Mono 导航字体 + active 状态 `#f0e0d8` 底色 |
