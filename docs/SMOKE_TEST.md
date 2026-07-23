# SMOKE TEST — Foclo

每次重构后逐项验证。

## 基础启动

- [ ] 应用正常启动，窗口 760×620
- [ ] 窗口无原生标题栏（frameless）
- [ ] 侧栏显示 6 个导航项（Timer, Todo, Records, Subjects, Export, Settings）
- [ ] 默认在 Timer 页，Timer 1 显示 Idle 状态

## 主题切换

- [ ] 点击 Dark 按钮 → 切换 Dark 模式，UI 颜色变化
- [ ] 再次点击 → 切回 Light 模式
- [ ] 连点 Dark 按钮 8 次 → 进入 Moss 模式（红色 #cc2200 主题）
- [ ] Moss 模式下侧栏品牌文字变为 "MOSS_SYS :: ONLINE"
- [ ] Moss 模式下 Dark 按钮变为 orbit 图标 + "Enable"
- [ ] 再次连点 8 次 → 退出 Moss 模式，恢复正常

## Timer（全屏模式）

- [ ] 选择 Subject → 输入 Description → 点 Start，计时器开始计时
- [ ] 计时中状态显示 Running，Start 按钮变为 Pause
- [ ] 点 Pause → 计时暂停，状态变为 Paused
- [ ] 点 Resume → 继续计时
- [ ] 点 Archive → 计时结束，保存记录
- [ ] Records 页面能看到新记录
- [ ] 添加 Timer Slot（点 + 号）→ 出现 Timer 2
- [ ] Timer 1 运行中时 Timer 2 不能启动（互斥）
- [ ] 删除 Timer Slot → 编号重新排列

## Compact 模式

- [ ] 点右上角四箭头 → 进入 Compact 模式
- [ ] 窗口缩小至 300×186
- [ ] Compact 面板居中显示当前计时信息
- [ ] 左右箭头切换 Slot → 循环（头到尾，尾到头）
- [ ] Compact 模式下 Start/Pause 正常工作
- [ ] Compact 模式下 Archive 正常工作
- [ ] 点展开按钮 → 恢复全屏 760×620
- [ ] 切换模式后计时状态保持一致

## Todo

- [ ] 切换到 Todo 页
- [ ] 输入 Subject + Description → 点 ✓ 添加
- [ ] 勾选 checkbox → 标记完成（划线）
- [ ] 点击开始按钮 → 跳转到 Timer 页并填入 Subject

## Records

- [ ] 切换到 Records 页
- [ ] 筛选器 Today / Week / Month / All 正常工作
- [ ] 内联添加记录（日期、Subject、Description、时间）
- [ ] 编辑记录（点 ✎）
- [ ] 删除记录（点 🗑）

## Subjects

- [ ] 切换到 Subjects 页
- [ ] 添加新 Subject（名称 + 颜色）
- [ ] 编辑 Subject
- [ ] 删除 Subject

## Settings

- [ ] 切换 Week starts on
- [ ] 切换 Default Slots 数量
- [ ] 切换 Auto Backup

## Code of Timing 弹窗

- [ ] 点击侧栏底部 "Code of Timing" → 弹出模态窗口
- [ ] 弹窗内容完整显示 5 条规则 + 签名
- [ ] 点背景或按 Escape → 关闭

## 数据持久化

- [ ] 添加 Todo / Record / Subject 后重启应用
- [ ] 数据仍在

## Export

- [ ] 切换到 Export 页
- [ ] 选择日期范围 + 格式 → 点 Export
