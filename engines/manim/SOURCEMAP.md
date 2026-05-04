# MaCode Engine Source Map: ManimCE

> 生成日期: 2026-05-04
> 引擎版本: 0.19.0 (via pip show manim)
> 适配层版本: 1.0.0

## WHITELIST: 推荐探索路径

| 标识 | 路径/命令 | 用途 | 优先级 |
|------|-----------|------|--------|
| CORE_SCENE | `$(python -c "import manim; print(manim.__path__[0])")/scene/scene.py` | Scene 基类，construct() 生命周期 | P0 |
| CORE_MOBJECT_GEOMETRY | `$(python -c "import manim; print(manim.__path__[0])")/mobject/geometry.py` | Circle, Square, Line 等几何体 | P0 |
| CORE_MOBJECT_TYPES | `$(python -c "import manim; print(manim.__path__[0])")/mobject/types/vectorized_mobject.py` | VMobject 基类，路径与贝塞尔曲线 | P0 |
| CORE_ANIMATION_CREATION | `$(python -c "import manim; print(manim.__path__[0])")/animation/creation.py` | Create, DrawBorderThenFill, Uncreate | P0 |
| CORE_ANIMATION_TRANSFORM | `$(python -c "import manim; print(manim.__path__[0])")/animation/transform.py` | Transform, ReplacementTransform | P0 |
| CORE_ANIMATION_INDICATION | `$(python -c "import manim; print(manim.__path__[0])")/animation/indication.py` | Flash, FocusOn, Indicate | P1 |
| CORE_RENDERER | `$(python -c "import manim; print(manim.__path__[0])")/renderer/` | 渲染管线与 OpenGL 后端 | P1 |
| UTIL_CAMERA | `$(python -c "import manim; print(manim.__path__[0])")/camera/` | 相机控制、取景与移动 | P1 |
| UTIL_TEX | `$(python -c "import manim; print(manim.__path__[0])")/mobject/text/tex_mobject.py` | MathTex, Tex LaTeX 渲染 | P1 |
| UTIL_NUMBER_LINE | `$(python -c "import manim; print(manim.__path__[0])")/mobject/graphing/number_line.py` | NumberLine, Axes 坐标轴 | P1 |
| UTIL_COORDINATE | `$(python -c "import manim; print(manim.__path__[0])")/mobject/graphing/coordinate_systems.py` | CoordinateSystem, Axes 抽象 | P1 |
| UTIL_COLOR | `$(python -c "import manim; print(manim.__path__[0])")/utils/color.py` | 颜色常量与工具 | P1 |
| ADAPTER_TEMPLATES | `engines/manim/src/templates/` | MaCode 场景基类模板（待创建） | P2 |
| ADAPTER_UTILS | `engines/manim/src/utils/` | ffmpeg_pipe 等工具封装（待创建） | P2 |

## BLACKLIST: 禁止/不建议探索

| 标识 | 路径/命令 | 原因 |
|------|-----------|------|
| DEPRECATED_GL | `manimlib/` | ManimGL 旧版 API，与 CE 分支不兼容 |
| TEST_SUITE | `$(python -c "import manim; print(manim.__path__[0])")/test/` | 测试代码，非 API 表面 |
| INTERNAL_CONFIG | `$(python -c "import manim; print(manim.__path__[0])")/_config/` | 全局配置黑魔法，修改会破坏渲染环境 |
| INTERNAL_UTILS | `$(python -c "import manim; print(manim.__path__[0])")/utils/` | 内部工具函数，非稳定公开 API |
| INTERNAL_MOBJECT_TYPES | `$(python -c "import manim; print(manim.__path__[0])")/mobject/types/` | VMobject 内部实现细节，易误触 |
| BUILD_ARTIFACT | `.agent/tmp/` | 中间产物，非源码 |
| NODE_MODULES | `node_modules/` | 非 Python 引擎目录 |
| VENV_DIR | `.venv/` | Python 虚拟环境，非源码 |

## EXTENSION: 待补充/可添加

| 标识 | 描述 | 状态 |
|------|------|------|
| ADAPTER_SCENE_BASE | `engines/manim/src/templates/scene_base.py` — MaCode CameraScene 模板 | TODO |
| ADAPTER_FFMPEG_PIPE | `engines/manim/src/utils/ffmpeg_pipe.py` — ffmpeg 管道编码工具 | TODO |
| ADAPTER_LATEX_HELPER | `engines/manim/src/utils/latex_helper.py` — LaTeX 辅助工具 | TODO |
| SHADER_PIPELINE | 自定义 GLSL 着色器接入 | TODO |
| AUDIO_SYNC | 音频节拍同步（BPM 驱动动画参数） | TODO |
| GPU_RENDER | CUDA/OpenCL 加速渲染 | WONTFIX |
