# MaCode Engine Source Map: ManimCE

> 生成日期: 2026-05-13
> 引擎版本: 0.20.1
> 适配层版本: 1.0.0
> 源码根目录: `.venv/lib/python3.13/site-packages/manim/`

## WHITELIST: 推荐探索路径

| 标识 | 路径/命令 | 用途 | 优先级 |
|------|-----------|------|--------|
| CORE_SCENE | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/scene/scene.py` | Scene 基类，construct() 生命周期 | P0 |
| CORE_MOBJECT_GEOMETRY | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/mobject/geometry/` | Circle, Square, Line, Arc, Polygon 等几何体（通过 `__init__.py` 统一导出） | P0 |
| CORE_MOBJECT_TYPES | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/mobject/types/vectorized_mobject.py` | VMobject 基类，路径与贝塞尔曲线 | P0 |
| CORE_ANIMATION_CREATION | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/animation/creation.py` | Create, DrawBorderThenFill, Uncreate | P0 |
| CORE_ANIMATION_TRANSFORM | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/animation/transform.py` | Transform, ReplacementTransform | P0 |
| CORE_ANIMATION_FADING | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/animation/fading.py` | FadeIn, FadeOut, FadeToColor | P0 |
| CORE_ANIMATION_MOVEMENT | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/animation/movement.py` | MoveToTarget, ComplexHomotopy | P1 |
| CORE_ANIMATION_INDICATION | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/animation/indication.py` | Flash, FocusOn, Indicate, Circumscribe | P1 |
| CORE_RENDERER | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/renderer/` | 渲染管线与 OpenGL 后端 | P1 |
| UTIL_CAMERA | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/camera/camera.py` | 相机控制、取景与移动 | P1 |
| UTIL_TEX | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/mobject/text/tex_mobject.py` | MathTex, Tex LaTeX 渲染 | P1 |
| UTIL_TEXT | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/mobject/text/text_mobject.py` | Text, Paragraph 文本渲染 | P1 |
| UTIL_NUMBER_LINE | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/mobject/graphing/number_line.py` | NumberLine, Axes 坐标轴 | P1 |
| UTIL_COORDINATE | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/mobject/graphing/coordinate_systems.py` | CoordinateSystem, Axes, ComplexPlane | P1 |
| UTIL_COLOR | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/utils/color/` | 颜色常量与工具（core.py, manim_colors.py） | P1 |
| CORE_3D | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/mobject/three_d/` | Sphere, Cube, Prism3D, Cylinder, Cone 等 3D 对象 | P1 |
| CORE_TABLE | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/mobject/table.py` | Table, MobjectTable 数据表格 | P1 |
| ADAPTER_TEMPLATES | `engines/manim/src/templates/` | MaCode 场景基类模板（待创建） | P2 |
| ADAPTER_AUDIO_SYNC | `engines/manim/src/utils/audio_sync.py` | 音频节拍同步读取器 | P2 |
| ADAPTER_UTILS | `engines/manim/src/utils/` | ffmpeg_pipe 等工具封装（待创建） | P2 |

## BLACKLIST: 禁止/不建议探索

| 标识 | 路径/命令 | 原因 |
|------|-----------|------|
| DEPRECATED_GL | `manimlib/` | ManimGL 旧版 API，与 CE 分支不兼容 |
| TEST_SUITE | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/utils/testing/` | 测试代码，非 API 表面 |
| INTERNAL_CONFIG | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/_config/` | 全局配置黑魔法，修改会破坏渲染环境 |
| INTERNAL_CLI | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/cli/` | CLI 内部实现，非 API |
| INTERNAL_PLUGINS | `$(.venv/bin/python -c "import manim; print(manim.__path__[0])")/plugins/` | 插件标志内部实现 |
| BUILD_ARTIFACT | `.agent/tmp/` | 中间产物，非源码 |
| NODE_MODULES | `node_modules/` | 非 Python 引擎目录 |
| VENV_DIR | `.venv/` | Python 虚拟环境，非源码 |

## EXTENSION: 待补充/可添加

| 标识 | 描述 | 状态 |
|------|------|------|
| ADAPTER_SCENE_BASE | `engines/manim/src/templates/scene_base.py` — MaCodeScene 基类（继承 MovingCameraScene，含路径注入/相机聚焦/音频同步） | DONE |
| ADAPTER_FFMPEG_PIPE | `engines/manim/src/utils/ffmpeg_builder.py` — ffmpeg 管道编码工具 | DONE |
| ADAPTER_LATEX_HELPER | `engines/manim/src/utils/latex_helper.py` — LaTeX 辅助工具（中文模板 / 公式工厂 / 预编译 / 错误诊断） | DONE |
| SHADER_PIPELINE | 自定义 GLSL 着色器接入 | DONE |
| AUDIO_SYNC | 音频节拍同步（BPM 驱动动画参数） | DONE |
| GPU_RENDER | CUDA/OpenCL 加速渲染 | WONTFIX |

## REDIRECT: Common Pitfall Corrections

When you find yourself writing the left column, use the right column instead.

| Pitfall | Correct Approach | Reason |
|---------|-----------------|--------|
| Hand-write `-vf "fade=..."` in Python strings | `utils.ffmpeg_builder.FFMpeg().video.fade(...)` | String concat error-prone; timing edge-case prone |
| Hand-write `-af "amix=..."` in Python strings | `utils.ffmpeg_builder.FFMpeg().audio.amix(...)` | Same as above |
| Hand-write `\begin{cases}` in MathTex | `utils.latex_helper.cases(...)` | MathTex default `align*` cannot nest `cases` |
| Hand-write `\begin{bmatrix}` in MathTex | `utils.latex_helper.matrix(...)` | Same nesting conflict |
| Hand-write `\begin{align*}` in MathTex | `utils.latex_helper.align_eqns(...)` | Double `align*` environment |
| Hand-write `gl_Position = ...` | `utils.shader_builder.Shader().node(...)` | GLSL compile errors decoupled from causes |
| Hand-write 60+ character regex | `utils.pattern_helper.pattern.xxx()` | Unreadable, edge-case prone |
| Hand-write raw ffmpeg command strings | `utils.ffmpeg_builder` | Bash variable expansion traps |
