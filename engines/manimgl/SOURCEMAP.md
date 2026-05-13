# MaCode Engine Source Map: ManimGL

> 生成日期: 2026-05-11
> 引擎版本: 1.7.2
> 适配层版本: 1.0.1
> 源码根目录: `.venv-manimgl/lib/python3.x/site-packages/manimlib/`

## WHITELIST: 推荐探索路径

| 标识 | 路径/命令 | 用途 | 优先级 |
|------|-----------|------|--------|
| CORE_SCENE | `manimlib/scene/scene.py` | Scene 基类，construct() 生命周期 | P0 |
| CORE_MOBJECT | `manimlib/mobject/mobject.py` | Mobject 基类，所有对象的根 | P0 |
| CORE_GEOMETRY | `manimlib/mobject/geometry.py` | Circle, Square, Line, Polygon 等几何体 | P0 |
| CORE_SHAPES | `manimlib/mobject/shape_matchers.py` | SurroundingRectangle, BackgroundRectangle | P1 |
| CORE_ANIMATION_CREATION | `manimlib/animation/creation.py` | ShowCreation, DrawBorderThenFill | P0 |
| CORE_ANIMATION_TRANSFORM | `manimlib/animation/transform.py` | Transform, ReplacementTransform | P0 |
| CORE_ANIMATION_FADING | `manimlib/animation/fading.py` | FadeIn, FadeOut, FadeToColor | P0 |
| CORE_ANIMATION_MOVEMENT | `manimlib/animation/movement.py` | MoveToTarget, ComplexHomotopy | P1 |
| CORE_ANIMATION_INDICATION | `manimlib/animation/indication.py` | Flash, FocusOn, Indicate | P1 |
| CORE_CAMERA | `manimlib/camera/camera.py` | 相机控制与取景 | P1 |
| CORE_TEX | `manimlib/mobject/svg/tex_mobject.py` | Tex, TextMobject LaTeX 渲染 | P1 |
| CORE_TEXT | `manimlib/mobject/svg/text_mobject.py` | Text 文本渲染 | P1 |
| CORE_NUMBER_LINE | `manimlib/mobject/number_line.py` | NumberLine 数轴 | P1 |
| CORE_COORDINATE | `manimlib/mobject/coordinate_systems.py` | Axes, ComplexPlane 坐标系 | P1 |
| CORE_COLOR | `manimlib/utils/color.py` | 颜色常量与工具 | P1 |
| CORE_3D | `manimlib/mobject/three_dimensions.py` | Sphere, Cube, Prism, Cylinder 等 3D 对象 | P1 |
| CORE_TABLE | `manimlib/mobject/table.py` | Table, MobjectTable 数据表格 | P1 |
| ADAPTER_TEMPLATES | `engines/manimgl/src/templates/` | MaCode 场景基类模板 | P2 |
| ADAPTER_UTILS | `engines/manimgl/src/utils/` | 音频同步等工具封装（待创建） | P2 |

## BLACKLIST: 禁止/不建议探索

| 标识 | 路径/命令 | 原因 |
|------|-----------|------|
| MANIMCE_API | `manim/` | ManimCE 社区版 API，与 ManimGL 不兼容 |
| MANIMCE_SCENE | `manim.scene` | ManimCE 的 Scene 体系，导入会导致冲突 |
| TEST_SUITE | `manimlib/utils/testing/` | 测试代码，非 API 表面 |
| INTERNAL_CONFIG | `manimlib/config.py` | 全局配置内部实现，修改会破坏环境 |
| INTERNAL_CLI | `manimlib/stream_starter.py` | CLI 内部启动器，非 API |
| INTERNAL_SHADER | `manimlib/shaders/` | GLSL 着色器内部目录，直接修改风险高 |
| BUILD_ARTIFACT | `.agent/tmp/` | 中间产物，非源码 |
| NODE_MODULES | `node_modules/` | 非 Python 引擎目录 |
| VENV_DIR | `.venv-manimgl/` | Python 虚拟环境，非源码 |

## EXTENSION: 待补充/可添加

| 标识 | 描述 | 状态 |
|------|------|------|
| ADAPTER_SCENE_BASE | `engines/manimgl/src/templates/scene_base.py` — MaCode Scene 模板 | DONE |
| ADAPTER_AUDIO_SYNC | `engines/manimgl/src/utils/audio_sync.py` — 音频节拍同步读取器 | DONE |
| ADAPTER_FFMPEG_PIPE | `engines/manimgl/src/utils/ffmpeg_builder.py` — ffmpeg 管道编码工具 | DONE |
| SHADER_PIPELINE | 自定义 GLSL 着色器接入 | DONE |
| AUDIO_SYNC | 音频节拍同步（BPM 驱动动画参数） | TODO |
| GPU_RENDER | CUDA/OpenCL 加速渲染 | WONTFIX |

## REDIRECT: Common Pitfall Corrections

When you find yourself writing the left column, use the right column instead.

| Pitfall | Correct Approach | Reason |
|---------|-----------------|--------|
| Hand-write `\begin{cases}` in MathTex | `utils.latex_helper.cases(...)` | MathTex default `align*` cannot nest `cases` |
| Hand-write `\begin{bmatrix}` in MathTex | `utils.latex_helper.matrix(...)` | Same nesting conflict |
| Hand-write `\begin{align*}` in MathTex | `utils.latex_helper.align_eqns(...)` | Double `align*` environment |
| Hand-write `gl_Position = ...` | `utils.shader_builder.Shader().node(...)` | GLSL compile errors decoupled from causes |
