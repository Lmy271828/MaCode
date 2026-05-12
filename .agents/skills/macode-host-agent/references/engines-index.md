# MaCode 引擎 API 参考索引

> 本索引聚合了所有通过符号链接集成到 `.agents/skills/` 的引擎参考 skill。
> Agent 按 `manifest.json` 的 `engine` 字段自动选择对应参考，无需记忆路径。

---

## 引擎选择速查

| manifest `engine` | 默认引擎推断 | 查阅 Skill | 核心参考路径 |
|-------------------|-------------|-----------|-------------|
| `manim` | `.py` 文件存在且无 `engine` 字段时默认 | `manimce-best-practices` | `rules/` (22 个主题) |
| `manimgl` | 显式声明或 `.py` + OpenGL 交互需求 | `manimgl-best-practices` | `rules/` (15 个主题) |
| `motion_canvas` | `.tsx` 文件存在时默认 | `motion-canvas` | `references/` (18 个主题) |
| *(composite)* | 各 segment 独立决定 | 按 segment 的 `engine` 分别查阅 | — |

---

## ManimCE (`engine: manim`)

**Skill**: `manimce-best-practices`
**入口**: `.agents/skills/manimce-best-practices/SKILL.md`

### 核心 Rules

| 主题 | 文件 | 典型查询 |
|------|------|---------|
| Scene 结构 | `rules/scenes.md` | `Scene` / `MovingCameraScene` / `ThreeDScene` |
| Mobject 类型 | `rules/mobjects.md` | `Circle`, `Square`, `VGroup`, `VMobject` |
| 创建动画 | `rules/creation-animations.md` | `Create`, `Write`, `FadeIn` |
| 变换动画 | `rules/transform-animations.md` | `Transform`, `ReplacementTransform` |
| 动画组合 | `rules/animation-groups.md` | `AnimationGroup`, `LaggedStart`, `Succession` |
| 文本 | `rules/text.md` | `Text`, `font_size`, `color` |
| LaTeX / Math | `rules/latex.md` | `MathTex`, `Tex`, 公式着色 |
| 文本动画 | `rules/text-animations.md` | `Write`, `AddTextLetterByLetter` |
| 颜色 | `rules/colors.md` | `BLUE`, `RED`, `ManimColor`, 渐变 |
| 样式 | `rules/styling.md` | `fill_opacity`, `stroke_width` |
| 定位 | `rules/positioning.md` | `move_to`, `next_to`, `align_to` |
| 分组布局 | `rules/grouping.md` | `VGroup`, `Group`, `arrange` |
| 坐标系 | `rules/axes.md` | `Axes`, `NumberPlane` |
| 绘图 | `rules/graphing.md` | `plot`, `parametric_curve` |
| 3D | `rules/3d.md` | `ThreeDScene`, `Sphere`, `Surface` |
| 时间控制 | `rules/timing.md` | `run_time`, `rate_func`, `lag_ratio` |
| 动态更新 | `rules/updaters.md` | `ValueTracker`, `add_updater` |
| 相机 | `rules/camera.md` | `MovingCameraScene`, `self.camera.frame` |
| CLI | `rules/cli.md` | `manim -pql`, 质量标志 |
| 配置 | `rules/config.md` | `manim.cfg`, 质量预设 |
| 形状 | `rules/shapes.md` | `Circle`, `Rectangle`, `Polygon` |
| 线条 | `rules/lines.md` | `Line`, `Arrow`, `Vector` |

### 关键差异（ManimCE vs ManimGL）

| Feature | ManimCE | ManimGL |
|---------|---------|---------|
| Import | `from manim import *` | `from manimlib import *` |
| CLI | `manim` | `manimgl` |
| Math text | `MathTex(r"\pi")` | `Tex(R"\pi")` |
| Scene | `Scene` | `InteractiveScene` |
| Create anim | `Create` | `ShowCreation` |

---

## ManimGL (`engine: manimgl`)

**Skill**: `manimgl-best-practices`
**入口**: `.agents/skills/manimgl-best-practices/SKILL.md`

### 核心 Rules

| 主题 | 文件 | 典型查询 |
|------|------|---------|
| Scene 结构 | `rules/scenes.md` | `InteractiveScene`, `Scene` |
| Mobject | `rules/mobjects.md` | `Mobject`, `VMobject`, `Group` |
| 动画 | `rules/animations.md` | `ShowCreation`, `FadeIn` |
| 创建动画 | `rules/creation-animations.md` | `ShowCreation`, `Write` |
| 变换 | `rules/transform-animations.md` | `Transform`, `TransformMatchingTex` |
| 动画组合 | `rules/animation-groups.md` | `LaggedStart`, `Succession` |
| LaTeX | `rules/tex.md` | `Tex`, raw strings `R"..."` |
| 文本 | `rules/text.md` | `Text`, `font_size` |
| t2c 着色 | `rules/t2c.md` | `tex_to_color_map` |
| 颜色 | `rules/colors.md` | `BLUE`, `RGB`, hex, GLSL |
| 样式 | `rules/styling.md` | `fill`, `stroke`, `backstroke` |
| 3D | `rules/3d.md` | `Sphere`, `Torus`, `parametric surfaces` |
| 相机 | `rules/camera.md` | `frame.reorient()`, Euler angles |
| 交互开发 | `rules/interactive.md` | `-se` flag, `checkpoint_paste()` |
| 帧控制 | `rules/frame.md` | `self.frame`, `reorient` |
| 嵌入调试 | `rules/embedding.md` | `self.embed()`, `touch()` |
| CLI | `rules/cli.md` | `manimgl -w -o -se` |
| 配置 | `rules/config.md` | `custom_config.yml` |

### 独有特性

- **交互模式**: `manimgl scene.py MyScene -se 20` — 在第 20 行处进入 IPython shell，状态保留
- **相机控制**: `self.frame.reorient(phi, theta, gamma, center, height)`
- **t2c 着色**: `Tex(R"E=mc^2", t2c={"E": BLUE})`
- **fix_in_frame**: 3D 运动中保持对象在屏幕空间固定

---

## Motion Canvas (`engine: motion_canvas`)

**Skill**: `motion-canvas`
**入口**: `.agents/skills/motion-canvas/SKILL.md`

### 核心 References

| 主题 | 文件 | 典型查询 |
|------|------|---------|
| 项目设置 | `references/SETUP.md` | `makeScene2D`, Vite 配置 |
| 布局 | `references/LAYOUT.md` | `Layout`, `FlexBox`, `Grid` |
| 文本 | `references/TXT.md` | `Txt`, `fontSize`, `fill` |
| LaTeX | `references/LATEX.md` | `Latex`, 公式渲染 |
| 形状 | `references/ICONS.md` | `Circle`, `Rect`, `Line` |
| SVG | `references/SVG.md` | `Svg`, 路径动画 |
| 媒体 | `references/MEDIA.md` | `Image`, `Video` |
| 相机 | `references/CAMERA.md` | `CameraView`, `zoom` |
| 过渡 | `references/TRANSFORMS.md` | `transform`, `morph` |
| 补间 | `references/TWEENING.md` | `createSignal`, tween |
| 弹簧 | `references/SPRINGS.md` | `spring`, 物理动画 |
| 渐变 | `references/GRADIENTS.md` | `Gradient`, `LinearGradient` |
| 滤镜 | `references/FILTERS.md` | `Blur`, `Brightness` |
| 效果 | `references/EFFECTS.md` | `Glow`, `Shadow` |
| 声音 | `references/SOUNDS.md` | `Audio`, `play` |
| 流程控制 | `references/FLOW_CONTROL.md` | `yield*`, `thread` |
| 渲染 | `references/RENDERING.md` | 导出设置, 格式 |
| 演示模式 | `references/PRESENTATION_MODE.md` | 幻灯片, 导航 |

### 关键概念

- **Generator 函数**: `function*` 定义， `yield` 暂停，`yield*` 委托
- **Signals**: `createSignal(3)` — getter/setter/tween 一体化
- **Refs**: `createRef<Circle>()` — 引用节点用于动画
- **ThreadGenerator**: 可组合的动画单元

---

## Manim Composer（视频规划）

**Skill**: `manim-composer`
**入口**: `.agents/skills/manim-composer/SKILL.md`

**用途**：在编写任何代码**之前**，将模糊的视频概念转化为详细的 scene-by-scene 计划。

**触发条件**：
- 用户想创建教育/解释视频
- 用户有模糊的概念需要可视化
- 用户提到 "3b1b style"

**输出格式**：`scenes.md` — 包含 Overview、Narrative Arc、逐 Scene 规划、Color Palette、Implementation Order

**参考**：
- `references/narrative-patterns.md` — 常见 3b1b 叙事结构
- `references/visual-techniques.md` — 有效可视化模式
- `references/scene-examples.md` — 示例 scenes.md 摘录

---

## 使用方式

### 方式一：按 manifest 自动选择（推荐）

```bash
cat scenes/01_demo/manifest.json | jq '.engine'
# → "manim"
# 自动查阅 .agents/skills/manimce-best-practices/SKILL.md 及其 rules/
```

### 方式二：关键词速查

```bash
# ManimCE: Circle 创建动画
cat .agents/skills/manimce-best-practices/rules/creation-animations.md | grep -A5 "Circle"

# ManimGL: 相机控制
cat .agents/skills/manimgl-best-practices/rules/camera.md | grep -A5 "reorient"

# Motion Canvas: Signal 补间
cat .agents/skills/motion-canvas/references/TWEENING.md | grep -A5 "createSignal"
```

### 方式三：macode inspect 互补使用

```bash
# 快速确认 API 存在性和基本签名
macode inspect --grep "Circle\|MathTex"

# 深入了解用法、示例和最佳实践
# → 查阅对应引擎 skill 的 rules/references
```

---

*本索引由 MaCode Harness 自动生成，符号链接指向 `manim_skill/` 和 `skills/` 仓库。*
*外部 skill 更新时，本索引内容自动同步。*
