---
name: layout-compiler
description: >
  MaCode Layout Compiler Skill。用于将内容清单自动编译为布局配置，再生成引擎场景源码。
  触发条件：(1) 需要创建标准结构的教学/演示场景，(2) 内容明确但不想手动编排布局，
  (3) 使用 lecture_3zones 等预定义布局模板，(4) 使用 definition_reveal 等预定义叙事模板。
---

# Layout Compiler Skill

你是 MaCode Layout Compiler 的**使用者 Agent**。你的角色是**约束求解器，非设计师**——你负责将明确的内容填入标准化的布局与叙事模板，而不是创造新的视觉语言。

## 核心原则

1. **内容驱动**：先写 `content_manifest.json`，再编译，最后微调
2. **模板优先**：复用现有的 layout + narrative 组合，不发明新结构
3. **约束即契约**：编译器报错时，修改内容或更换模板，不绕过约束
4. **人工作为最后一步**：编译生成的 `scene.py` 中的 TODO 注释需要人工补充

## content_manifest.json 规范

```json
{
  "title": "场景标题（仅元数据）",
  "content": [
    {"type": "text", "text": "纯文本", "importance": "high|medium|low"},
    {"type": "formula", "latex": "\\lim_{x \\to a} f(x) = L", "importance": "high"},
    {"type": "visual", "primitive": "NumberLine", "params": {"x_range": [-5, 5]}, "importance": "high"}
  ],
  "layout_profile": "lecture_3zones",
  "narrative_profile": "definition_reveal"
}
```

### type 说明

| type | 必需字段 | 可选字段 | 引擎映射 |
|------|---------|---------|---------|
| `text` | `text` | — | Text (Manim) / Txt (MC) |
| `formula` | `latex` | — | Tex/MathTex (Manim) / Latex (MC) |
| `visual` | `primitive` | `params` | 见 visual-primitives.json |

### importance 说明

- `high`：优先分配，尽量放入 primary zone
- `medium`：默认级别，在 high 之后分配
- `low`：最后分配，多余时可能被舍弃

### 可用 primitive 列表（ engines/manimgl/src/templates/visual-primitives.json ）

| Primitive | ManimGL | ManimCE | Motion Canvas |
|-----------|---------|---------|---------------|
| Text | Text | Text | Txt |
| Tex | Tex | MathTex | Latex |
| Circle | Circle | Circle | Circle |
| Square | Square | Square | Rect |
| Rectangle | Rectangle | Rectangle | Rect |
| NumberLine | NumberLine | NumberLine | Line |
| Axes | Axes | Axes | **未映射** |
| Arrow | Arrow | Arrow | Line |
| Vector | Vector | Arrow | Line |
| Line | Line | Line | Line |
| Polygon | Polygon | Polygon | **未映射** |
| Dot | Dot | Dot | Circle |

未映射 primitive 在编译时生成 TODO 注释，不导致失败。

## 标准工作流

```bash
# 1. 编写内容清单
scenes/{name}/content_manifest.json

# 2. 编译布局
bin/layout-compile.py scenes/{name}/content_manifest.json \
  --output scenes/{name}/layout_config.yaml

# 3. （可选）检查 layout_config.yaml，确认分配正确

# 4. 编译场景源码
bin/scene-compile.py scenes/{name}/layout_config.yaml \
  --engine manimgl \
  --output scenes/{name}/scene.py

# 5. 补充 TODO 注释处的内容

# 6. 渲染
macode render scenes/{name}/
```

## 三个完整示例

### 示例 1：definition_reveal（概念首次引入）

```json
{
  "title": "极限的定义",
  "content": [
    {"type": "text", "text": "极限的定义", "importance": "high"},
    {"type": "formula", "latex": "\\lim_{x \\to a} f(x) = L", "importance": "high"},
    {"type": "visual", "primitive": "NumberLine", "params": {"x_range": [-5, 5]}, "importance": "high"},
    {"type": "text", "text": "对于任意 \\epsilon > 0...", "importance": "medium"}
  ],
  "layout_profile": "lecture_3zones",
  "narrative_profile": "definition_reveal"
}
```

叙事顺序：
1. `statement` (title) → 出标题文字
2. `visual` (main_visual) → 出公式 + 数轴
3. `annotation` (annotation) → 出注释文字
4. `example` (main_visual) → 出示例图形（需补充）

### 示例 2：build_up_payoff（推导构造）

```json
{
  "title": "勾股定理的证明",
  "content": [
    {"type": "text", "text": "勾股定理", "importance": "high"},
    {"type": "visual", "primitive": "Square", "params": {"width": 2}, "importance": "high"},
    {"type": "visual", "primitive": "Rectangle", "params": {"width": 3, "height": 4}, "importance": "high"},
    {"type": "visual", "primitive": "Line", "importance": "high"},
    {"type": "visual", "primitive": "Polygon", "importance": "high"},
    {"type": "text", "text": "a² + b² = c²", "importance": "high"}
  ],
  "layout_profile": "lecture_3zones",
  "narrative_profile": "build_up_payoff"
}
```

叙事顺序：setup → build_1 → build_2 → build_3 → payoff → reflection

### 示例 3：wrong_to_right（纠偏深化）

```json
{
  "title": "常见的积分误区",
  "content": [
    {"type": "text", "text": "误区：积分就是求面积", "importance": "high"},
    {"type": "visual", "primitive": "Axes", "params": {"x_range": [-3, 3]}, "importance": "high"},
    {"type": "text", "text": "实际上，积分是黎曼和的极限...", "importance": "medium"},
    {"type": "visual", "primitive": "Circle", "importance": "high"}
  ],
  "layout_profile": "lecture_3zones",
  "narrative_profile": "wrong_to_right"
}
```

叙事顺序：wrong → failure → refinement → correct

## 错误诊断指南

### 约束冲突时的处理流程

```
[layout-compile] ERROR: Constraint violation
  Zone 'title': max_objects=2, allocated=3
  Suggestion: Move excess objects from 'title' to another zone...
```

**处理步骤**：
1. 阅读错误信息，确认违反的约束类型
2. 阅读 Suggestion，了解修复方向
3. 修改 `content_manifest.json`：
   - 减少该 zone 对应类型的内容数量
   - 降低非关键内容的 `importance`
   - 或更换 `narrative_profile` 以获得更多/不同的 stage
4. 重新运行 `layout-compile.py`

### 常见错误速查

| 错误 | 原因 | 修复 |
|------|------|------|
| `Zone 'X': max_objects=N, allocated=M` | 某 zone 内容过多 | 减少匹配该 zone stage 的内容，或降低 importance |
| `Total text characters ... exceeds limit` | 文字总量超限 | 精简文字，拆分场景 |
| `Primary zone 'main_visual' must have at least one visual` | 主视觉区无图形 | 添加 `type: visual` 内容 |
| `Primitive "X" is not mapped for Motion Canvas` | MC 不支持该图元 | 更换 primitive 或手写 MC 代码 |

## 何时不使用 Compiler

Compiler 是**可选工具**，以下情况建议手写 `scene.py`：
- 需要非标准布局（不使用 lecture_3zones）
- 需要复杂动画序列（非 stage-by-stage）
- 需要自定义过渡效果
- 内容是探索性的，结构和内容同时迭代
