# 方向 C：Shader Pipeline 跨引擎复用 — 详细规划

> **目标**：让 ManimGL 的 GLSL shader builder 生成的着色器能够被 batch 引擎（ManimCE）复用，形成 "Shader 开发 → 素材化 → 嵌入生产" 的闭环。
>
> **核心范式**：Shader-as-Asset（着色器素材化）。ManimGL 定位为 "Shader IDE"，产出的是可复用的预渲染素材，而非运行时代码注入。
>
> **渲染器决策**：采用 **纯 moderngl 方案**（已弃用 glslViewer）。moderngl 提供 `create_standalone_context()`，零窗口依赖，直接渲染到 offscreen framebuffer，输出像素完全可控。

---

## C.0 现状分析与核心洞察

### ManimGL 内置着色器体系

ManimGL 拥有极为精良的着色器基础设施：

| 机制 | 说明 | 复用价值 |
|------|------|----------|
| **文件夹级组织** | `manimlib/shaders/{name}/{vert,frag,geom}.glsl` | 每个 shader 是自包含模块，可直接提取 |
| **#INSERT 代码复用** | `inserts/emit_gl_Position.glsl`、`finalize_color.glsl` 等 | 共享函数库，提取时需展开为自包含代码 |
| **moderngl 封装层** | `shader_wrapper.py` 统一管理编译、uniform、texture、VAO | uniform/schema 可序列化，为素材化提供元数据 |
| **内置 Shader 库** | quadratic_bezier(f/stroke/depth)、surface、textured_surface、true_dot、image、fractal | 大量现成效果可直接素材化 |

### 当前割裂点

- **ManimGL**：interactive-only，OpenGL 实时渲染，不输出帧序列，但拥有完整的 shader 开发和调参能力
- **ManimCE**：batch-only，确定性帧输出，但 OpenGL 管线封闭，无法注入自定义 GLSL
- **Motion Canvas**：2D Canvas/WebGL 管线，与 GLSL 完全不兼容

### 核心洞察

> 不要尝试在运行时桥接两个引擎的 OpenGL 管线（成本极高且 fragile）。
> 让 ManimGL 成为 **Shader IDE**：开发、调参、预览 → 导出素材 → batch 引擎消费预渲染结果。

这与 Motion Canvas 的 "创作-生产" 双轨制完全一致：
- MC：`macode dev`（Vite HMR 创作）→ `macode render`（Puppeteer batch 产出）
- Shader：人工调参可用 `node experimental/shader-preview/shader-preview.mjs <id>`（实验性）→ `macode shader render`（moderngl batch 产出）

---

## C.1 双层架构：Layer 1（PNG 帧）+ Layer 2（Shader 素材）

MaCode 的核心契约是 **PNG 帧序列**（`frame_%04d.png`）。Shader Pipeline 不打破这一契约，而是将其分为两层：

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 2: Shader Asset（可复用、可参数化、可再编辑）                   │
│  ├─ shader.json: 元数据 + uniform 声明 + 节点图                       │
│  ├─ vert.glsl / frag.glsl: 自包含 GLSL 源码                          │
│  └─ preview.png: 静态预览图                                          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ 编译（moderngl headless runner）
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1: PNG Frame Sequence（MaCode 一等公民，管道原生消费）         │
│  ├─ frame_0001.png ... frame_0090.png                               │
│  ├─ 可被 concat.sh 编码为 MP4                                       │
│  ├─ 可被 check-static.py --layer layer2 质检                        │
│  ├─ 可被 concat.sh 编码为 MP4                                       │
│  └─ 可被 composite-unified-render.py 做硬切拼接                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Layer 1 为什么是一等公民

`pipeline/` 工具链（`render.sh`, `concat.sh`, `check-static.py` 等）只认识 PNG 帧序列。将 shader 输出也纳入 Layer 1，意味着：
- **零管道改造**：现有 `concat.sh` 的 ffmpeg 编码无需修改
- **质检统一**：`check-static.py --layer layer2` 的 layout 分析对 shader 帧和普通场景帧一视同仁
- **合成兼容**：shader 帧序列可直接作为 `composite` 的 segment 输入

### Layer 2 为什么是一等公民

Layer 2 是"源代码级"资产，支持：
- **参数重调**：修改 `shader.json` 中的 `uniforms` 后重新编译，无需重写场景代码
- **跨项目复用**：`assets/shaders/{name}/` 目录可整体复制到新项目
- **节点图重建**：`nodegraph` 字段保留原始 `shader_builder` 链，支持"素材再编辑"
- **分辨率适配**：同一 Layer 2 可编译为 1080p / 4K / 竖屏等不同 Layer 1

---

## C.2 Shader-as-Asset 格式规范 (shader.json v1.0)

### 目录结构

```
assets/shaders/{name}/
├── shader.json          # 元数据 + 参数声明 + 渲染配置
├── vert.glsl            # 自包含顶点着色器（#INSERT 已展开）
├── frag.glsl            # 自包含片元着色器
├── geom.glsl            # [可选] 几何着色器
├── preview.png          # 静态预览图（第 0 帧）
└── frames/              # [可选] 预编译 Layer 1 缓存
    ├── frame_0001.png
    └── ...
```

### shader.json Schema

```json
{
  "schema_version": "1.0",
  "metadata": {
    "name": "noise_heatmap",
    "description": "Simplex noise with heatmap colorization",
    "author": "MaCode Shader Builder",
    "source": "manimgl_builtin|builder_nodegraph|handwritten",
    "created_at": "2026-05-08T12:00:00Z"
  },
  "backend": {
    "target": "gpu|d3d12|cpu|headless",
    "glsl_version": "#version 430",
    "noise_impl": "simplex"
  },
  "glsl": {
    "vertex": "vert.glsl",
    "fragment": "frag.glsl",
    "geometry": null
  },
  "uniforms": [
    {
      "name": "time",
      "type": "float",
      "default": 0.0,
      "animation": {
        "enabled": true,
        "from": 0,
        "to": 10,
        "easing": "linear",
        "unit": "seconds"
      }
    },
    {
      "name": "resolution",
      "type": "vec2",
      "default": [1920, 1080],
      "animation": { "enabled": false }
    }
  ],
  "render": {
    "fps": 30,
    "duration": 3.0,
    "resolution": [1920, 1080],
    "output_format": "png_sequence"
  },
  "nodegraph": {
    "builder_version": "1.0",
    "nodes": [
      {"type": "noise", "name": "noise0", "params": {"frequency": 3.0, "octaves": 4}},
      {"type": "colorize", "name": "colorize0", "params": {"palette": "heatmap", "source": "noise0_value"}}
    ]
  }
}
```

### 关键设计决策

| 决策 | 理由 |
|------|------|
| `#INSERT` 展开为自包含 GLSL | 外部渲染器（moderngl）不识别 manimlib 的 `#INSERT` 语义 |
| `uniforms` 显式声明动画参数 | headless 渲染器据此自动生成 time 曲线，无需场景代码干预 |
| `nodegraph` 字段可选保留 | 允许从素材反向重建 `shader_builder` 链，实现"素材再编辑" |
| `source` 字段标记来源 | 内置 shader 提取需记录原始路径，便于追溯和更新 |
| `frames/` 作为预编译缓存 | Layer 2 → Layer 1 的编译结果可复用，避免重复渲染 |

---

## C.3 ManimGL 内置着色器提取与模块化

### C.3.1 提取器设计

`engines/manimgl/src/utils/shader_extractor.py`：

```python
def extract_builtin_shader(shader_name: str) -> dict:
    """
    从 manimlib/shaders/{shader_name}/ 提取完整 shader。
    自动展开 #INSERT 指令，输出自包含 GLSL。
    
    Returns:
        {
            "vert": str,      # 展开后的顶点着色器
            "frag": str,      # 展开后的片元着色器  
            "geom": str|None, # 展开后的几何着色器
            "inserts": list,  # 用到的 inserts 清单
            "uniforms": list  # 从代码静态分析提取的 uniform 声明
        }
    """
```

**#INSERT 展开算法**：
1. 读取 `vert.glsl` / `frag.glsl` / `geom.glsl`
2. 正则匹配 `^#INSERT ([\w/]+\.glsl)$`
3. 从 `manimlib/shaders/inserts/` 读取对应文件
4. 递归处理 inserts 中的嵌套 `#INSERT`（当前无嵌套，但防御性处理）
5. 替换原行，输出自包含代码

### C.3.2 内置 Shader 素材化优先级

| 内置 Shader | 类型 | 适用场景 | 优先级 | 复杂度 |
|-------------|------|----------|--------|--------|
| `image/` | 2D 图像 | 图像处理滤镜、后处理 | **P1** | 低（无 geom） |
| `quadratic_bezier/fill` | 2D 矢量 | 形状填充效果 | **P1** | 中（#INSERT 多） |
| `quadratic_bezier/stroke` | 2D 矢量 | 描边效果 | **P1** | 中 |
| `surface/` | 3D 参数 | 参数曲面渲染 | P2 | 高（需 camera uniform） |
| `textured_surface/` | 3D 参数 | 贴图曲面 | P2 | 高（需 texture 输入） |
| `true_dot/` | 2D 点 | 粒子/点阵效果 | P2 | 中（含 geom shader） |
| `mandelbrot_fractal/` | 2D 数学 | 曼德勃罗集可视化 | P3 | 低 |
| `newton_fractal/` | 2D 数学 | 牛顿分形可视化 | P3 | 低 |

### C.3.3 三层模块化复用机制

MaCode Shader Library 采用三层复用架构：

**Layer 1: Insert 层（GLSL 级）**
- 保留 `#INSERT` 的语义概念，但展开为物理文件
- `emit_gl_Position.glsl` → 所有 2D shader 共用投影函数
- `finalize_color.glsl` → 颜色空间转换/gamma 校正共用
- `complex_functions.glsl` → 复数运算数学库
- 提取器生成 `inserts/` 子目录，记录依赖关系

**Layer 2: 节点层（API 级）**
- `shader_builder.py` 的 `NODE_REGISTRY` 是核心复用单元
- 每个 `ShaderNode` 子类是自包含 GLSL 生成器，可任意组合
- 新增预设节点扩展库（见 C.7.3）

**Layer 3: 素材层（文件级）**
- `assets/shaders/` 目录是最终复用单元
- 完整 shader 目录可复制到任意项目
- `_registry.json` 提供全局搜索、标签、预览索引

---

## C.4 Headless 渲染器：纯 moderngl 方案

### C.4.1 为什么弃用 glslViewer

| 问题 | 影响 |
|------|------|
| WSL2 下窗口/viewport 只展示一半 | 渲染输出可能被裁剪，像素不可控 |
| 依赖 GLFW/X11/EGL | 即使 `--headless` 也有窗口管理层介入 |
| 命令行 uniform 注入语法不明确 | 交互式命令（`-e` / stdin）行为不稳定 |
| 需要额外编译安装 | 增加用户入门门槛 |

**结论**：glslViewer 是一个优秀的 shader 开发沙盒，但不适合作为 MaCode 的确定性 batch 渲染器。moderngl 提供完全可控的 Python-native 替代方案。

### C.4.2 moderngl Headless Runner 架构

```python
# engines/manimgl/src/utils/shader_runner.py
import moderngl
import numpy as np
from PIL import Image

class HeadlessShaderRunner:
    """
    基于 moderngl 的 headless shader 渲染器。
    
    不依赖窗口系统，直接操作 OpenGL offscreen framebuffer。
    输出像素尺寸 = 代码设定，无裁剪风险。
    """
    
    def __init__(self, width: int, height: int):
        # 创建独立 OpenGL context（无窗口、无 X11）
        self.ctx = moderngl.create_standalone_context()
        # 在 GPU 内存中分配离屏 framebuffer
        self.fbo = self.ctx.framebuffer(
            color_attachments=[self.ctx.texture((width, height), 4)]
        )
        self.width = width
        self.height = height
        # 构建全屏 quad（两个三角形覆盖 NDC [-1,1]x[-1,1]）
        self._build_fullscreen_quad()
    
    def render(self, vert: str, frag: str, uniforms: dict) -> np.ndarray:
        """渲染单帧，返回 numpy RGBA array。"""
        prog = self.ctx.program(vertex_shader=vert, fragment_shader=frag)
        # 注入 uniforms
        for name, value in uniforms.items():
            if name in prog:
                prog[name].value = value
        # 绑定 framebuffer、清屏、绘制 quad
        self.fbo.use()
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)
        self._vao.render(moderngl.TRIANGLES)
        # 读取像素（OpenGL 原点在左下角，需要垂直翻转）
        img = Image.frombytes('RGBA', (self.width, self.height), self.fbo.read(components=4))
        return np.array(img.transpose(Image.FLIP_TOP_BOTTOM))
    
    def render_sequence(self, vert: str, frag: str,
                        uniforms_frames: list[dict],
                        output_dir: str,
                        prefix: str = "frame") -> list[str]:
        """批量渲染帧序列，输出 frame_%04d.png。"""
        ...
```

### C.4.3 与 MaCode 后端体系的集成

`shader_backend.py` 的 4 级后端（GPU / D3D12 / CPU / HEADLESS）直接映射到 moderngl context 创建策略：

| 后端 | moderngl 行为 | GLSL 版本 |
|------|--------------|-----------|
| `gpu` | `create_standalone_context()` 自动选择硬件加速 | `#version 430` |
| `d3d12` | 同 gpu（Mesa D3D12 作为默认 GL driver） | `#version 430` |
| `cpu` | `create_standalone_context()` 回退到 llvmpipe | `#version 330` |
| `headless` | 同 cpu；若 context 创建失败则输出 placeholder 帧 | `#version 330` |

**实际验证**（当前 WSL2 环境）：
- `.venv/bin/python` + `create_standalone_context()` → `llvmpipe (LLVM 20.1.2)`
- 320×240 全屏红 quad 渲染成功，输出像素精确可控
- 不依赖 X11、GLFW、EGL

---

## C.5 ManimCE 桥接：ShaderMobject

### C.5.1 设计目标

让 ManimCE 场景代码可以像使用普通 Mobject 一样使用 shader 素材：

```python
from utils.shader_bridge import ShaderMobject

class ShaderProductionScene(MaCodeScene):
    def construct(self):
        # 方式1：引用已预渲染的 Layer 1 帧序列
        shader = ShaderMobject("assets/shaders/noise_heatmap/")
        self.play(FadeIn(shader))
        self.wait(3)
        
        # 方式2：从 Layer 2 素材运行时编译为 Layer 1
        shader = ShaderMobject(
            "assets/shaders/noise_heatmap/",
            render=True, duration=3, fps=30
        )
        self.play(FadeIn(shader))
        
        # 方式3：与常规 Mobject 混排
        title = Text("Noise Field", font_size=48)
        shader = ShaderMobject("assets/shaders/noise_heatmap/")
        self.play(Write(title))
        self.play(FadeIn(shader.next_to(title, DOWN)))
        self.wait(2)
```

### C.5.2 实现方案

`engines/manim/src/utils/shader_bridge.py`：

```python
from manim import ImageMobject
from PIL import Image
import numpy as np
import json
import os

class ShaderMobject(ImageMobject):
    """
    将 shader 预渲染帧序列（Layer 1）包装为 ManimCE Mobject。
    
    继承 ImageMobject，通过 updater 根据 scene 时间驱动帧切换，
    实现 shader 动画在 ManimCE 场景中的无缝嵌入。
    """
    
    def __init__(
        self,
        shader_path: str,
        render: bool = False,
        duration: float | None = None,
        fps: float | None = None,
        loop: bool = True,
        **kwargs
    ):
        self.shader_path = shader_path
        self.shader_json = self._load_shader_json()
        
        # 自动触发 Layer 2 → Layer 1 编译（如果 frames/ 不存在）
        if render or not self._has_prerendered_frames():
            self._prerender(duration=duration, fps=fps)
        
        # 加载第一帧作为 ImageMobject 初始状态
        first_frame = self._get_frame_path(0)
        super().__init__(first_frame, **kwargs)
        
        # 注册时间驱动 updater
        self.add_updater(self._frame_updater)
    
    def _frame_updater(self, mob, dt):
        """根据场景 elapsed_time 计算帧索引，懒加载对应图片。"""
        if not hasattr(self, 'start_time'):
            self.start_time = self.scene.time
        
        elapsed = self.scene.time - self.start_time
        frame_idx = self._time_to_frame(elapsed)
        
        frame_path = self._get_frame_path(frame_idx)
        if os.path.exists(frame_path):
            img = Image.open(frame_path).convert("RGBA")
            self.pixel_array = np.array(img)
    
    def _time_to_frame(self, t: float) -> int:
        """时间 → 帧索引，支持 loop / once。"""
        fps = self.shader_json["render"]["fps"]
        total = self._get_total_frames()
        frame = int(t * fps)
        return frame % total if self.loop else min(frame, total - 1)
```

**关键技术细节**：

| 问题 | 方案 |
|------|------|
| 内存占用 | **懒加载**：只保留当前帧 pixel_array，逐帧 `Image.open()` |
| 帧切换卡顿 | PIL 预解码 `convert("RGBA")`，避免运行时格式转换 |
| 与 Manim 动画配合 | 继承 `ImageMobject`，支持 `FadeIn`/`FadeOut`/`Transform` |
| 时间同步 | 记录 `start_time = scene.time`，与 Manim 动画时间轴对齐 |
| 多实例 | 每个实例独立维护 frame index |

---

## C.6 Motion Canvas 桥接

Motion Canvas 天然支持 `Video` 节点。Layer 2 素材编译为 MP4 后可直接嵌入：

```tsx
import {Video, makeScene2D} from '@motion-canvas/2d';
import {createRef} from '@motion-canvas/core';

export default makeScene2D(function* (view) {
  const shaderVideo = createRef<Video>();
  view.add(
    <Video
      ref={shaderVideo}
      src="assets/shaders/noise_heatmap/frames.mp4"
      size={[1920, 1080]}
    />
  );
  yield* shaderVideo().play(3);
});
```

**MC 路径的特殊性**：
- MC 偏好视频文件（MP4）而非 PNG 序列
- `bin/shader-render.py` MC 分支默认输出 MP4（通过 ffmpeg 后处理 Layer 1 帧序列）
- `engines/motion_canvas/src/utils/shader_bridge.ts`：薄包装 `Video` 组件

---

## C.7 Shader Library 与生态建设

### C.7.1 目录结构与注册表

```
assets/shaders/
├── _registry.json           # 全局索引
├── _presets/                # 节点预设模板
│   ├── glow.json
│   ├── blur.json
│   └── vignette.json
├── noise_heatmap/           # builder 生成示例
│   ├── shader.json
│   ├── vert.glsl
│   ├── frag.glsl
│   └── preview.png
├── mandelbrot/              # 提取的内置 shader
│   └── ...
└── custom/                  # 用户自定义 shader
    └── ...
```

### C.7.2 CLI 接口设计

```bash
# 列出可用 shader
macode shader list [--tag noise] [--source builtin]

# 渲染 shader 到 Layer 1 帧序列
macode shader render assets/shaders/noise_heatmap/ \
    --fps 30 --duration 3 --resolution 1920x1080 \
    --output .agent/tmp/shader_frames/

# 从 ManimGL 内置 shader 提取为 Layer 2 素材
macode shader extract quadratic_bezier/fill \
    --output assets/shaders/extracted/qb_fill/

# 注册 shader 到库
macode shader register assets/shaders/my_custom/

# 批量预渲染库中所有 shader（生成 Layer 1 缓存）
macode shader render-all --fps 30
```

### C.7.3 节点预设扩展

扩展 `shader_builder.py` 的 `NODE_REGISTRY`：

```python
NODE_REGISTRY = {
    # === 现有节点 ===
    "noise": NoiseNode,
    "gradient": GradientNode,
    "colorize": ColorizeNode,
    "oscillate": TimeOscillateNode,
    
    # === P1 新增：后处理效果 ===
    "glow": GlowNode,                    # 高斯模糊 + 叠加辉光
    "blur": GaussianBlurNode,            # 可调半径高斯模糊
    "vignette": VignetteNode,            # 边缘暗角
    "chromatic_aberration": ChromaNode,  # RGB 通道分离
    
    # === P2 新增：扭曲/变形 ===
    "displacement": DisplacementNode,    # 噪声位移扭曲
    "ripple": RippleNode,                # 水波纹
    "lens_distortion": LensDistortNode,  # 鱼眼/桶形畸变
}
```

---

## C.8 实施路线图

### P0：Shader Export + Headless Render（核心闭环）

| # | 任务 | 文件 | 验收标准 |
|---|------|------|----------|
| C-EXP | 扩展 `shader_builder.save()` 输出 `shader.json` | `engines/manimgl/src/utils/shader_builder.py` | `save(dir)` 生成 `shader.json` + `.glsl` |
| C-EXT | 内置 shader 提取器 | `engines/manimgl/src/utils/shader_extractor.py` | `extract_builtin_shader("quadratic_bezier/fill")` 返回自包含 GLSL |
| C-RUN | Headless 渲染器 | `engines/manimgl/src/utils/shader_runner.py` | 接收 `shader.json` + uniform，输出 numpy RGBA array / PNG |
| C-CLI | 统一渲染 CLI | `bin/shader-render.py` | 接收 `shader.json` 路径，输出 `frames/frame_%04d.png` |
| C-VAL | 验证场景 | `scenes/07_shader_demo/` | ManimGL 预览 → export → moderngl render → PNG 像素级对比 |

### P1：ManimCE Bridge（嵌入生产）

| # | 任务 | 文件 | 验收标准 |
|---|------|------|----------|
| C-BRI | ShaderMobject | `engines/manim/src/utils/shader_bridge.py` | ManimCE 场景 `FadeIn(ShaderMobject("..."))` 正常播放 shader 动画 |
| C-SCE | 生产验证场景 | `scenes/08_shader_production/` | 场景同时包含 Text、Circle、ShaderMobject，渲染输出正确 |
| C-CMD | `macode shader` 子命令 | `bin/macode` | 支持 `list`/`render`/`extract` |

### P2：Shader Library + 生态（复用扩展）

| # | 任务 | 文件 | 验收标准 |
|---|------|------|----------|
| C-LIB | Shader Library 目录 + 注册表 | `assets/shaders/` + `_registry.json` | `macode shader list` 输出可用 shader 清单 |
| C-NODE | 扩展 NODE_REGISTRY | `engines/manimgl/src/utils/shader_builder.py` | glow、blur、vignette 节点可用 |
| C-MC | Motion Canvas 桥接 | `engines/motion_canvas/src/utils/shader_bridge.ts` | MC 场景可引用 shader MP4 |
| C-DOC | 文档更新 | `AGENTS.md` | Shader Pipeline 使用文档完整 |

---

## C.9 风险登记册

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| moderngl standalone context 在纯 CPU CI 环境失败 | 中 | 中 | 探测失败时输出 placeholder 帧；与现有 headless 机制一致 |
| GLSL `#version` 与 moderngl 支持的 OpenGL 版本不匹配 | 低 | 中 | shader_backend.py 已有 4 级适配；渲染前探测可用版本 |
| 预渲染帧体积过大 | 中 | 中 | P2 支持 MP4 输出路径；帧缓存复用机制 |
| ManimCE ImageMobject updater 逐帧 I/O 卡顿 | 低 | 中 | 懒加载 + PIL 预解码；短时长场景无感知 |
| `#INSERT` 循环依赖（未来 manimlib 版本） | 低 | 低 | 提取器检测循环并报错；当前内置 shader 无循环 |

---

## C.10 与现有架构的集成点

| 现有组件 | 集成方式 | 变更量 |
|----------|----------|--------|
| `shader_builder.py` | `save()` 扩展为输出 `shader.json` | 小（+20 行） |
| `shader_backend.py` | 新增 `to_dict()` / `from_dict()` 用于序列化 | 小（+15 行） |
| `bin/detect-hardware.sh` | 新增 moderngl context 可用性探测 | 小（+5 行） |
| `engines/manim/scripts/render.sh` | 渲染前注入 `PYTHONPATH` 已覆盖 shader_bridge.py | 零变更 |
| `pipeline/render.sh` | 识别 `manifest.json` 中 `shader_assets` 字段 | 中（+30 行） |
| `pipeline/concat.sh` | 无需变更，shader Layer 1 输出与普通帧序列格式一致 | 零变更 |
| `bin/macode` | 新增 `shader` 子命令分支 | 中（+50 行） |
| `api-gate.py` | 新增 shader 代码静态检查 | 小（+10 行） |

---

*规划版本：v1.1（glslViewer 已弃用，改用纯 moderngl）*
*日期：2026-05-08*
*状态：P0 实施中*
