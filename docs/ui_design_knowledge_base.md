# PyQt5 UI 设计知识库

> 基于 GitHub 50+ 个现代 PyQt/PySide 项目分析总结

## 一、最佳参考项目

### 主题框架（可即插即用）
| 项目 | Stars | 特点 | 适用场景 |
|------|-------|------|---------|
| [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) | 5k+ | 微软 Fluent Design，完整组件库，明/暗主题切换 | 需要完整现代组件库时首选 |
| [PyDracula](https://github.com/Wanderson-Magalhaes/Modern_GUI_PyDracula_PySide6_or_PyQt6) | 7k+ | 暗紫主题，圆角，动画侧边栏，自定义标题栏 | 经典现代 GUI 模板 |
| [Qt-Material](https://github.com/UN-GCPDS/qt-material) | 2.8k | Material Design，26 种主题（明/暗），运行时切换 | 轻量主题化 |
| [PyQt-SiliconUI](https://github.com/ChinaIceF/PyQt-SiliconUI) | 1.1k | 国产，灵动优雅，自定义动画控件 | 精美控件库 |
| [QDarkStyleSheet](https://github.com/ColinDuquesnoy/QDarkStyleSheet) | 3k+ | 最成熟的暗色主题，覆盖所有 Qt 控件 | 成熟稳定 |
| [qtmodern](https://github.com/gmarull/qtmodern) | 748 | 扁平现代化，简洁 | 快速美化 |

### 完整应用参考
| 项目 | 特点 |
|------|------|
| [Groove 音乐播放器](https://github.com/zhiyiYo/Groove) | Fluent Design，毛玻璃效果，流畅动画 |
| [CQ-editor](https://github.com/CadQuery/CQ-editor) | 专业 CAD 界面，停靠窗口，工具栏，状态栏 |
| [Dashboard-PyQt5](https://github.com/AbdouSadou/dashboard-qt5) | 数据仪表盘，动画开关，亮暗主题切换 |

## 二、核心设计原则

### 1. 布局原则
- **三分栏布局**：左侧导航/列表(20-30%) | 中间内容(45-55%) | 右侧面板(20-25%)
- **卡片式设计**：内容分组用白色卡片 + 圆角8px + 浅阴影
- **留白充足**：元素间距至少 12-16px，不要拥挤
- **响应式**：窗口缩放时各面板比例合理，最小宽度 1000px

### 2. 色彩体系（浅色主题）
```
主色: #4a90d9 (蓝色) — 按钮、选中态、链接
辅色: #5cb85c (绿色) — 成功、完成
背景: #f5f6fa — 整体背景
卡片: #ffffff — 卡片、面板
边框: #e1e4e8 — 分割线、边框
主文字: #2c3e50 — 标题、正文
次文字: #7f8c8d — 辅助信息、标签
危险: #e74c3c — 删除、错误
警告: #f39c12 — 待处理
链接: #3498db — 可点击文字
```

### 3. 按钮设计
```
普通状态: 主色背景 + 白色文字 + 圆角6px + padding 8px 16px
Hover: 背景色加深(主色*0.85) + 轻微上浮(translateY(-1px)) + 阴影
Pressed: 背景色更深 + 无阴影
Disabled: 灰色背景 + 浅色文字
过渡: 所有状态切换用 0.2s ease 过渡
图标按钮: 圆角4px，hover 时背景变浅
```

### 4. 字体排版
```
标题: 16-20px, 加粗, #2c3e50
正文: 13-14px, 常规, #333
辅助: 11-12px, 常规, #7f8c8d
代码/日志: 等宽字体(Consolas/Source Code Pro), 12px
字体族: -apple-system, "Microsoft YaHei", "Segoe UI", sans-serif
```

### 5. 控件样式
**输入框 (QLineEdit):**
```
border: 1px solid #ddd, border-radius: 6px, padding: 8px 12px
focus: border-color: #4a90d9 + 浅蓝色外发光
```

**下拉框 (QComboBox):**
```
类似输入框，下拉箭头用 ▼ 字符
hover 时边框变色
```

**进度条 (QProgressBar):**
```
圆角 4px，渐变色(主色→辅色)
高度 6-8px，文字居中标示百分比
```

**滚动条 (QScrollBar):**
```
宽度 8px，圆形滑块，hover 时变宽
背景透明
```

**卡片 (QFrame/Card):**
```
background: white, border-radius: 8px
box-shadow: 0 2px 8px rgba(0,0,0,0.06)
hover: 阴影加深(0 4px 16px rgba(0,0,0,0.1))
```

### 6. 动画与交互
- 按钮 hover: 背景色渐变 + 轻微上浮 (0.2s ease)
- 卡片 hover: 阴影加深 (0.25s ease)
- 标签切换: 下划线滑动动画
- 进度条: 平滑过渡
- 弹窗: fade in + 缩放 (0.2s ease)
- 侧边栏: 滑动展开/收起 (0.3s ease)

## 三、专门针对 AI 文档批处理工具的设计方案

### 布局结构
```
+----------------------------------------------------------+
| [📄 AI 文档批处理]  [+文件] [+文件夹] [▶开始] [⚙设置]    |  ← 工具栏 56px
+----------+-------------------------------+----------------+
|          |   对比  |  原文  |  结果       |  模板选择       |
| 文件列表  |                               |  ┌───────────┐  |
| (30%)    |   ┌───────┬───────┐          |  │ 📖 中译英  │  |
|          |   │ 原文   │ 结果   │          |  ├───────────┤  |
| 📁 1.docx |   │        │        │          |  │ 📝 学术润色│  |
| 📁 2.pdf  |   │        │        │          |  ├───────────┤  |
| 📁 3.txt  |   │        │        │          |  │ ✏️ 自定义  │  |
|          |   └───────┴───────┘          |  └───────────┘  |
|          |                               |  温度 ═══●══    |
|          |                               |  max_tokens ══●═|
+----------+-------------------------------+----------------+
| [═══████████░░░░░░░░░═══] 75% | 预计 30 秒 | 日志窗口      |  ← 底部状态
+----------------------------------------------------------+
```

### 工具栏设计
- 高度 48-56px，白色背景，底部浅灰分割线
- 左侧：应用名称 + logo（emoji 📄）
- 中间：操作按钮组（带 emoji 图标）
- 右侧：设置按钮
- 按钮之间间距 8px

### 文件列表面板
- 标题栏："文件列表" + 计数徽章 (3)
- 拖拽区域：虚线边框 + "拖拽文件到此处"
- 文件项：文件图标(emoji) + 文件名 + 状态色点
- 右键菜单
- 底部筛选下拉框

### 预览区域（核心）
- 三标签：对比 | 原文 | 结果
- 对比模式：QSplitter 左右分栏，可拖拽
- 文档模式：QWebEngineView 渲染 Word 风格
- 底部导出按钮组

### 模板面板
- 简洁卡片网格，每行 1 个
- 选中高亮（蓝色边框）
- 自定义模板展开文本框
- 参数滑条

## 四、Qt 实现技巧

### QSS 变量模拟
Qt 不支持 CSS 变量，用类名模拟：
```css
/* 在顶层 widget 设置属性 */
MainWindow { qproperty-primaryColor: #4a90d9; }

/* 或使用 qt-material 的 XML 主题文件 */
```

### QPushButton 动画
Qt 不支持 CSS transition，用 QPropertyAnimation：
```python
anim = QPropertyAnimation(btn, b"maximumWidth")
anim.setDuration(200)
anim.setStartValue(100)
anim.setEndValue(200)
anim.start()
```

或通过 QSS 的伪状态实现视觉反馈：
```css
QPushButton:hover {
    background-color: #357abd;
}
QPushButton:pressed {
    background-color: #2a6cb5;
    padding-top: 9px;
    padding-bottom: 7px;
}
```

### 阴影实现
```python
shadow = QGraphicsDropShadowEffect()
shadow.setBlurRadius(12)
shadow.setOffset(0, 2)
shadow.setColor(QColor(0, 0, 0, 30))
widget.setGraphicsEffect(shadow)
```

### 全局面板样式
```python
panel.setStyleSheet("""
    QFrame#panel {
        background: white;
        border: 1px solid #e1e4e8;
        border-radius: 8px;
    }
""")
```

## 五、参考截图要点

| 参考 | 可借鉴点 |
|------|---------|
| ilovepdf.com | 浅色背景，卡片化工具，清晰的功能分区，充足留白 |
| PyDracula | 圆角按钮，动画侧边栏，现代化色彩 |
| Fluent Design (Microsoft) | 丙烯酸/毛玻璃效果，流畅动画，明暗主题 |
| Material Design (Google) | 卡片层级，阴影系统，动效曲线 |
