# Alangrapher · UI Spec

> **作用**：这个文件是 UI 需求的唯一真相源。微信对话可以丢，这个文件不能过期。
> **更新规则**：每次 UI 讨论的结论实时写入，不要事后补。标注日期。
> **读取规则**：每次 `/new` 后 Moss 第一件事是读这个文件。

---

## 🎯 设计方向

- **主题**：Liquid Glass（#5E6AD2 靛蓝主色，柔和蓝灰面）。不做多主题切换。
- **平台**：macOS 优先（未来迁移 Windows，框架由 Moss 选定）
- **窗口尺寸**：760 × 620
- **字体**：中文 UI = HarmonyOS Sans SC（已安装，brew font-harmonyos-sans-sc）。计时数字 = JetBrains Mono（等宽，防跳变）。拉丁 fallback = Inter / sans-serif。
- **深色模式**：已实现。`html.dark` class 切换整套 CSS 变量。色值见颜色令牌段。
- **Moss 模式（彩蛋）**：第三套主题。JetBrains Mono 全局、红琥珀单色系、零绿色、终端语法（`MOSS_SYS :: ONLINE` 顶栏）、**light 暖象牙白底色**（不用 dark）。**呼出方式：Dark/Light 按钮 2 秒内连击 8 次**。色值见颜色令牌段。

---

## ✅ 已确认（Done）

### 导航图标 — 全部 SVG 化
- **出处**：用户 2026-06-12：「这些icon的线条都不是等粗的吗」→ 选方案 2「全部换成 SVG」
- **状态**：✅ 已确认
- **详情**：6 个导航图标，18×18 画布，1.5px 描边、圆头圆角、`stroke="currentColor"`
  - Timer：钟面 + 指针，Todo：圆角方框 + 勾，Records：三条横线，Subjects：四格方块，Export：下箭头 + 底线，Settings：齿轮

### 按钮图标 — SVG 化 + 风格统一
- **出处**：用户 2026-06-12：「start 按钮 icon 和 archive 的按钮 icon 风格也不一致」
- **状态**：✅ 已确认
- **详情**：Start ▶ fill / Archive Download Tray stroke / Pause 两个圆角矩形。全部 1.5px 描边、圆头圆角，和侧边栏图标统一。

### 精简模式（Compact Mode）
- **出处**：用户 2026-06-12：「精简模式下icon大小也可以再小一点，线条细一点」
- **修订**：2026-06-17 用户：「compact模式下的排版布局再调整一下 稍微宽松一点」
- **状态**：✅ 已确认
- **详情**：
  - **面板尺寸**：300px 宽，24px 内边距，圆角 14px
  - **计时数字**：32px JetBrains Mono bold
  - **按钮**：padding 8px 14px，间距 10px，圆角 8px，图标 14px
  - **badge**：10px 字号，2px 8px 内边距
  - **居中方式**：**JS 直设 absolute + translate(-50%,-50%)**（CSS class 切换在跨浏览器环境下不可靠；直接操作 style 属性确保精确居中）
  - **切换逻辑**：点 Compact → sidebar + content `style.display = 'none'`，面板 `position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%)`。点 Expand → 清除所有内联 style 恢复

### Slot 收起/展开
- **出处**：用户 2026-06-12：「点击收起后会怎么样」
- **状态**：✅ 已确认
- **详情**：▲ 收起 → ▼ → 时钟+按钮折叠，只剩 header。点 ▼ → 恢复。

### ① 「Code of Timing」彩蛋
- **出处**：用户 2026-06-12：「红框的文字改成 Code of Timing，点击后出那个彩蛋内容」
- **状态**：✅ 已确认
- **详情**：放在页面**左下角**，代替原来的 "local timer tracker"。内容：「Alangrapher's code of timing」。不做 dark mode 限制。

### ② Slot 增加按钮
- **出处**：用户 2026-06-12：「timer 页面缺少增加 slot 的按钮，slot 最多允许增加五个」
- **状态**：✅ 已确认
- **详情**：+ 按钮（虚线框 + 号），右侧 slot-header 内，hover 变紫。默认 1 个，最多 5 个。

### ③ Archive 行为 — 清零
- **出处**：用户 2026-06-12：「archive 后清零」
- **状态**：✅ 已确认
- **详情**：点击 Archive → 保存当前时间到 Records → 清零时钟 → 回到 Idle。

### ④ Records 条目双击 → 回填 slot
- **出处**：用户 2026-06-12：「timer 下的 today's records 条目，双击可以重新进入计时」
- **状态**：✅ 已确认（行为已修正）
- **详情**：双击 Records 条目 → 将该条目 subject/description **回填到一个空闲 slot**，但不自动开始。用户仍需手动点 Start。
- **修正记录**：2026-06-12 用户纠正——不要自动开始计时，只是占据 slot。

### ⑤ 多 Slot 互斥逻辑
- **状态**：✅ 已确认
- **详情**：同一时间只有一个计时器能跑——激活一个 slot，其他自动 pause。

### ⑥ Code of Timing 弹窗样式
- **出处**：用户 2026-06-12：「规则N的字体要比规则正文的字体小一点，规则正文的字体再大一点」→ 2026-06-12 追加：「英文字体用 Apple Chancery 花体统一」
- **修订**：2026-06-17 用户：「code of timing页面所有内容居中显示」
- **状态**：✅ 已确认
- **详情**：
  - **字体层级**：标题 "计时准则" = Songti SC 24px bold / 规则正文 = Songti SC 15px / 规则编号 = HarmonyOS Sans SC 13px bold `#5E6AD2` / 所有英文（Code of Timing / 引用 / 英译 / 署名）= **Apple Chancery** 花体
  - **字号**：Code of Timing 14px / 引用中文 14px 斜体、英文 13px 斜体 / 英译 13px / 署名 18px
  - **行间距**：规则正文 1.85× / 英译 margin-top: 2px / 规则间距统一 16px
  - **全文居中**：.modal-rule、.modal-rule-no、.modal-rule-zh、.modal-rule-en 全部 text-align: center
  - **署名**：Alan Zhu 居中，Apple Chancery 18px，主题色
  - **交互**：无关闭按钮，点击窗外关闭

### ⑦ Compact 面板行为
- **出处**：用户 2026-06-12：「在完整模式中存在几个 time slot 的，在压缩模式下都能够切换到」
- **状态**：✅ 已确认
- **详情**：
  - 面板显示**所有 timer slot**（含 Idle / Running / Paused），箭头 ← → 循环切换
  - 动作按钮按状态变化：Idle→Start+Archive / Running→Pause+Archive / Paused→Resume+Archive
  - 首尾边界箭头自动隐藏（Timer 1 无 ←，最后一个无 →）
  - 状态 badge 随切换更新（idle灰/running绿/paused黄）

### ⑧ 按钮强调色统一
- **出处**：用户 2026-06-12：「按钮颜色根据 Linear 风格调整」
- **状态**：✅ 已确认
- **详情**：Start / Archive / Pause / Resume 全部用 `#5E6AD2` 底 + 白色文字。不用黑底。

### ⑨ 图标对调修正
- **出处**：用户 2026-06-12：「上周的 Compact 图标修复」
- **状态**：✅ 已确认
- **详情**：Compact ⇄ Expand 图标对调（shrink ⇄ expand）。Dark ⇄ Light 图标：月亮 ⇄ 太阳。

### ⑨-A 全部 SVG 图标参考（Lucide 2px stroke）
- **出处**：用户 2026-06-16：「侧边栏的ICON替换，计入spec」
- **状态**：✅ 已确认
- **详情**：所有结构性和按钮图标统一使用 Lucide SVG，2px stroke，`stroke-linecap="round"` `stroke-linejoin="round"`，24×24 viewBox。inline 操作字符（✎🗑✓✕）保持 Unicode。

| 图标 | Lucide icon | 用途 |
|------|------------|------|
| Timer | `lucide-timer` (圆+表针+刻度线) | 侧边栏导航 |
| Todo | `lucide-list-todo` (勾选框+三条横线) | 侧边栏导航 |
| Records | `lucide-scroll-text` (卷轴+文字行) | 侧边栏导航 |
| Subjects | `lucide-swatch-book` (色本书) | 侧边栏导航 |
| Export | `lucide-folder-input` (文件夹+箭头) | 侧边栏导航 & Export 按钮 |
| Settings | `lucide-bolt` (六角形+内圆) | 侧边栏导航 |
| Dark | `lucide-moon-star` (月亮+星) | 主题切换按钮 |
| Light | `lucide-sun` (太阳+射线) | 主题切换按钮 |
| Moss (连击触发) | `lucide-orbit` (轨道+星点) | Moss 模式激活时显示，点击退出 |
| Start/Play | `lucide-play` (三角) | 开始计时按钮 |
| Pause | `lucide-pause` (双竖条) | 暂停按钮 |
| Archive | `lucide-panel-bottom-close` (向下箭头) | 归档按钮 |
| Compact | `lucide-shrink` (四角收缩) | Compact 按钮 |
| Expand | `lucide-expand` (四角展开) | Expand 按钮 |
| Chevron left | `lucide-chevron-left` | Compact panel 左箭头（替换 ‹） |
| Chevron right | `lucide-chevron-right` | Compact panel 右箭头（替换 ›） |
| Chevron down | `lucide-chevron-down` | Timer slot 折叠（替换 ▲） |
| Plus | `lucide-plus` | Timer 加 slot（替换 +） |
| Close/X | `lucide-x` | Timer slot 关闭（替换 ✕） |
| Arrow up-right | `lucide-arrow-up-right` | Export 按钮（替换 ↗） |

### ⑩ 计时器大数字字体
- **出处**：用户 2026-06-12：「计时器大数字加 JetBrains Mono，防数字跳」
- **状态**：✅ 已确认
- **详情**：`.timer-clock` 和 `.compact-clock` 使用 `font-family: 'JetBrains Mono', monospace`，等宽 + tabular-nums。

### ⑪ Records 页面 — 编辑 / 手动添加 / 删除 / 日期列动态显隐
- **出处**：用户 2026-06-12：「Record 页面需要增加编辑 record 以及手动添加、删除的功能」
- **修订**：2026-06-22 新增日期列根据筛选器动态显隐 + Date 列置首
- **状态**：✅ 已确认
- **详情**：
  - **手动添加**：表格上方 inline 表单行（Date/Subject▼/Description/Start/End → ✓）
    - Date 字段仅在筛选器为 This Week / This Month / All 时显示
    - 筛选器为 Today 时隐藏 Date 字段，默认填入当天日期
    - Duration 不显示——由 Start/End 自动计算（`calcDur()`）
  - **日期列（Date）**：
    - 筛选器为 Today → Date 列隐藏（CSS class `records-date-col` `display:none`）
    - 筛选器为 This Week / This Month / All → `.records-scroll-wrap` 加 `showing-dates` class → Date 列 `display:table-cell`
    - Date 列始终是表格第一列（`<th class="records-date-col">Date</th>` 在 Subject 之前）
  - **横向滚动**：表格容器 `.records-scroll-wrap { overflow-x: auto }`，列宽超出时自动出现滚动条
  - **行内编辑**：hover 行 → ✎ → 单元格变 input/select（含 Date 列 `type="date"`）→ ✓ 保存 / ✕ 取消
  - **删除**：hover 行 → 🗑 → 直接删除
  - **操作图标**：默认隐藏，hover 显示

### ⑫ Todo 页面 — inline 添加 + 状态切换 + Timer 跳转
- **出处**：用户 2026-06-12：「添加 todo 条目的方式不要用 add 按钮，而是在列表顶部允许直接输入，回车确认」
- **修订**：2026-06-17 修复 inline handler 的 HTML 引号断裂 bug；2026-06-22 新增双字段输入（Subject + Description）、checkbox 勾选完成（打✓ + 删除线）、▶ 按钮跳转 Timer
- **状态**：✅ 已确认
- **详情**：
  - **inline 添加**：列表顶部双字段行（Subject + Description），✓ 确认或 Enter 提交
  - **状态切换**：每条目前方 checkbox，点击 → 填充✓ + 文字加删除线 → counter 动态更新（n pending · m done）
  - **Timer 跳转**：未完成条目 hover 显示 ▶ 播放按钮（Lucide play SVG，14px），点击 → 切换到 Timer 页面，将 subject/description 填入第一个 slot → 自动设为 Running 状态
  - **列表风格**：border-bottom 底线分隔，hover 浅底，无卡片背景
  - **计数器格式**：{n} pending · {m} done

### ⑬ Subjects 页面 — inline 添加 + 编辑 / 删除
- **出处**：用户 2026-06-12：「subject 页面，+new 按钮也根据 record 页面的逻辑进行修改，同时列表尾部增加修改和删除」
- **状态**：✅ 已确认
- **详情**：
  - 去除 header `+ New` 按钮
  - 列表顶部 inline 添加行：色块（8色调色板，点击弹出） + 名称 input → ✓
  - 行尾 ✎ / 🗑 hover 显示，编辑模式行内 input + ✓ / ✕
  - 计数器自动更新

### ⑭ Export 页面 — 格式重排 + 预览替换
- **出处**：用户 2026-06-13：「输出方式调整为，排序改成 excel、markdown、json；preview 内容改为上次输出时间」
- **状态**：✅ 已确认
- **详情**：
  - 格式顺序：Excel（.xlsx）→ Markdown → JSON
  - 去除 CSV 预览数据，改为 "Last Export" 卡片显示最近导出时间（初始 "No exports yet"）

### ⑮ Settings 页面 — 新选项 + 删旧
- **出处**：用户 2026-06-13：「1. Auto-start timer 去掉 2. 增加默认 time slot 数量下拉 1-5 3. 增加自动备份+开关 4. data location 改自动备份地址允许选择」
- **状态**：✅ 已确认
- **详情**：
  - 删除 "Auto-start timer"
  - 新增 "Default time slots"：下拉 1–5，默认 3
  - 新增 "Auto backup"：toggle 开关 + "Backup location" 路径显示 + "Choose…" 按钮
  - "Data location" → "Backup location"，用户可点 Choose 修改路径
  - 顺序：Week starts on → Compact by default → Default time slots → Auto backup → Backup location → Reset all data

### ⑯ 列表风格统一（Todo / Records / Subjects）
- **出处**：2026-06-17 用户：「todo/records/subjects 的列表风格统一，添加方式也统一为inline添加」
- **状态**：✅ 已确认
- **详情**：
  - **三页共用视觉规则**：
    - 每行 `border-bottom: 1px solid var(--border)` 分隔，末行无底线
    - hover `background: var(--hover)` 浅底高亮
    - `padding: 8px 4px`，无卡片背景、无圆角、无阴影
  - **Records 特殊处理**：保持 `<table>` 结构（JS 依赖 `<tr>/<td>`），去除外层 `.card` 包装，表行加 hover，padding 收紧至 8px 4px
  - **Subjects 特殊处理**：保留色块 dot，行样式对齐 Todo
  - **Inline 添加统一**：三页添加区均去除卡片背景（`background: var(--card); border; border-radius`），改用纯 `border-bottom` 底线分隔。Records 保留多字段行（date/subject/desc/start/end/dur + confirm），Subjects 保留色块调色板

---

## ⏳ 待确认（Waiting Review）

<!-- 目前全部确认完毕。新需求从聊天记录提取后放这里 -->

---

## 🔲 待实现（Backlog）

- ~~Dark mode 切换~~ → ✅ 原型已实现（`html.dark` CSS 变量）
- 系统托盘驻留
- Windows 平台适配
- 深色模式监听（darkdetect）
- ~~Todo 页面功能~~ → ✅ 原型已实现（inline 输入 + Enter 添加）
- ~~Subjects 管理（增删改）~~ → ✅ 原型已实现（inline 添加 + 色块 + hover 编辑/删除）
- ~~Export 导出~~ → ✅ 原型已实现（Excel/Markdown/JSON）
- ~~Settings 配置项~~ → ✅ 原型已实现（Week starts / Compact by default / Default Slots / Auto Backup / Backup Location / Minimize to Tray / Reset）
- 键盘快捷键

---

## 📐 原型文件

- **原型路径**：`~/Projects/Alangrapher/prototype.html`
- **原型 == 设计稿**。Python 代码必须对齐原型，不应出现原型里没有的视觉决策。
- **本地预览**：`python3 -m http.server 8766` 在项目目录 → `http://localhost:8766/prototype.html`

---

## 🧭 导航（Sidebar）

| # | 页面 | 状态 |
|---|------|------|
| 1 | Timer | ✅ |
| 2 | Todo | ✅ |
| 3 | Records | ✅ |
| 4 | Subjects | ✅ |
| 5 | Export | ✅ |
| 6 | Settings | ✅ |

- 侧边栏宽度：**200px**
- 全部 SVG 图标：1.5px stroke / round caps / `currentColor` / 18×18 画布

---

## 🎨 颜色令牌（Liquid Glass）

| 用途 | 色值 |
|------|------|
| 主色（accent） | `#5E6AD2` |
| 运行中（running） | `#34C98B` |
| 暂停（paused） | `#F0B73F` |
| 空闲（idle） | `#9AA0AD` |
| 危险（danger） | `#D64430` |
| 💡 Dark 背景 | `#0D1117` / 侧栏 `#161B22` / 卡片 `#1C2128` |
| 💡 Dark 文字 | `#E6EDF3` / 副 `#8B949E` / muted `#6E7681` |
| 💡 Dark accent | `#6E7AE6` / hover `#8B90F8` |
| 💡 Dark 边框 | `#30363D` / hover `#21262D` |
| 🎯 Moss 背景 | `#f8f6f5` / 侧栏 `#f2efed` / 卡片 `#ffffff` / body `#ebe5e2` |
| 🎯 Moss 文字 | `#1a1a1f` / 副 `#8b5555` / muted `#a08080` |
| 🎯 Moss accent | `#cc2200` (MOSS 红) |
| 🎯 Moss 状态 | running `#cc2200` / paused `#b86644` / idle `#8b5555` |
| 🎯 Moss 边框 | `#d5c8c5` / hover `#f0e8e6` |
| 🎯 Moss 字体 | JetBrains Mono 全局，无 fallback |
| 🎯 Moss 规则 | 零绿色、零阴影、3px 左红条（sidebar + card）、顶栏 `MOSS_SYS :: ONLINE`、按钮 hover 红底白字 |

---

## 🖼️ 图标规范

- **全部 SVG 内联**，不使用 Unicode 字符图标
- **完整模式**：`stroke-width="1.5"` `stroke-linecap="round"` `stroke-linejoin="round"` `stroke="currentColor"`
  - 导航：18×18 | 按钮：14×14 | Slot 操作（▲✕+）：14×14
- **紧凑模式**：图标 12px、描边 1.2px
- **图标对调**：Compact（shrink）⇄ Expand（expand）已交换；Dark（月亮）⇄ Light（太阳）已交换

---

## 📝 关键交互规则

- **Slot 系统**：默认 1 个，最多 5 个；同一时间只跑一个计时器
- **Slot 操作**：▲ 收起 / ✕ 删除 / + 新增
- **Archive**：保存到 Records → 清零时钟 → 回到 Idle
- **Records 双击**：回填 subject/description 到空闲 slot → **不自动开始**，手动点 Start
- **Compact 面板**：显示所有 slot（含 Idle/Paused），← → 箭头循环切换；动作按钮按状态变化（Idle→Start / Running→Pause / Paused→Resume）；首尾箭头自动隐藏
- **Compact 面板尺寸**：300px 宽，24px 内边距，14px 圆角，32px 时钟，10px badge
- **Compact/Expand 互斥**：点击 Compact → sidebar + content style.display = none，面板 position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%)
- **Compact 按钮**：仅保留 `lucide-shrink` 图标，无文字标签，title 提示 "Compact mode"

---

## 📝 更新日志

| 日期 | 变更 |
|------|------|
| 2026-06-12 08:43 | 从方案选定到 UI 迭代全过程（12 轮修改） |
| 2026-06-12 14:51 | 创建 SPEC.md + DECISIONS.md，建立 Spec 驱动工作流 |
| 2026-06-12 22:30 | 从聊天记录 PDF 提取需求，填充 ⏳ Waiting Review |
| 2026-06-12 22:45 | 用户逐条确认 5 项需求，全部移至 ✅ Done；修正第 4 条行为 |
| 2026-06-12 23:30 | 字体换 HarmonyOS Sans SC；计时数字 JetBrains Mono；弹窗样式确定；Compact 面板支持所有 slot 切换；按钮色统一 #5E6AD2；图标对调修正 |
| 2026-06-12 23:50 | Code of Timing：中文正文 → Songti SC 宋体；所有英文 → Apple Chancery 花体；署名 Alan Zhu 花体 18px |
| 2026-06-13 00:10 | Records：手动添加/行内编辑/删除三功能；Todo：inline input + Enter 添加 |
| 2026-06-13 00:20 | Subjects：inline 添加 + 色块调色板 + 行内编辑/删除 |
| 2026-06-13 00:30 | Export：格式重排 Excel/Markdown/JSON；Settings：删 Auto-start、加 time slots/auto backup/Choose path |
| 2026-06-13 00:40 | Dark mode 完成：`html.dark` CSS 变量全量切换，6 页覆盖 |
| 2026-06-13 01:00 | Moss mode 纯血版：JetBrains Mono 全局、零绿色、终端语法、NOMINAL/ACTIVE/PAUSED |
| 2026-06-13 21:30 | Moss mode 从 dark 黑底改为 light 暖象牙白底（`#f8f6f5`），去除 CRT 扫描线，零阴影，3px 左红条 |
| 2026-06-14 01:30 | 原型全面对齐 SPEC：字体→HarmonyOS Sans SC、侧栏 184→200px、弹窗字体层级（Songti SC+Apple Chancery）、去 Close 按钮、Dark mode 改用 `html.dark` CSS class + SPEC 令牌色值、Unicode 图标全换 SVG（Dark/Light/Compact/Expand）、Todo/Subjects 去 +New 按钮换 inline 输入、Export 加 JSON 三格式、Settings 补全 7 项（Week starts on/Compact by default/Default Slots/Auto Backup/Backup Location/Minimize to Tray/Reset） |
| 2026-06-16 20:00 | 侧边栏 + 按钮图标全换 Lucide 2px 24×24 SVG（§9-A 参考表）；Moss mode 按钮改为 `lucide-orbit` |
| 2026-06-16 20:30 | 四项 UI 微调：① Dark 按钮 icon 与文字 flex 居中对齐；② Timer 标题与 Today 行 `flex-end` 基线对齐；③ Compact 按钮去文字仅保留图标；④ Compact/Expand 互斥——Compact 模式 `display:none` 藏内容区，Compact 卡片居中，两者不同时可见 |
| 2026-06-17 15:00 | ① Compact 面板放宽：300px、24px 内边距、32px 时钟、JS 直设 absolute 居中；② Code of Timing 全文居中（`text-align: center` 所有规则 + 间距统一 16px）；③ Todo 修复 HTML 引号断裂 bug（`addTodo()` 命名函数 + Unicode 实心点）；④ §16 三页列表风格统一（border-bottom 底线 + hover 浅底 + 去卡片背景 + inline 添加区统一） |
| 2026-06-22 | ① Todo：双字段添加（Subject/Description）、checkbox 完成状态、▶ 按钮跳转到 Timer 并自动启动；② Records：Duration 字段去除改自动计算；③ Records：Date 列根据筛选器动态显隐（Today 隐藏、其他显示）+ 横向滚动 `overflow-x:auto`；④ Records：Date 列置为表格第一列 |
