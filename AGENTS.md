# MaCode —— UNIX 原生的数学动画制作 Harness

> **设计信条**：Bash is all you need. Text is the universal interface. Make it work, then make it right, then make it fast.
>
> **名称来源**：Ma = Math（数学）+ Code（代码），亦致敬 UNIX 传统中简洁的命名哲学。

---

## 1. 项目愿景

MaCode 是一个 UNIX 原生的数学动画工具集（Harness）。它不封装高级 API，而是提供一套**可被任何 Host Agent（Claude Code、Cursor、Kimi 等）直接调用的 CLI 工具**，通过标准 Bash 命令完成数学动画的渲染、剪辑、压缩等全部环节。

核心目标：
- **引擎无关**：场景定义与引擎实现解耦。今天用 ManimCE，明天可迁移到 Motion Canvas，只需修改一行 `manifest.json`。
- **管道透明**：渲染、剪辑、压缩的每一步都是可见的文件转换，Host Agent 随时可以 `ls .agent/tmp/frames/` 检查中间状态。
- **状态可逆**：所有变更通过 Git 控制，错误是廉价的。
- **音频统一**：所有音频处理由 `ffmpeg` 完成，不引入额外依赖。
- **Host Agent 零侵入**：MaCode 不试图控制 Host Agent 的执行环境，只提供可被直接调用的独立 CLI。

> **💡 Skill 入口**：MaCode 提供结构化 skill（`.agents/skills/macode-host-agent/SKILL.md`），包含系统提示、工作流模板和示例。任何 Host Agent 都可直接读取该文件获取渐进式指导。

---

## 2. UNIX 设计原则（核心哲学）

### 2.1 做一件事并做好
- **渲染引擎**只输出帧序列（PNG / rawvideo）。
- **ffmpeg**负责所有音视频编码、剪辑、滤镜、格式转换。
- **Agent**只负责生成场景源码与编排命令。
- **Git**只负责版本控制与状态回滚。
- 绝不内建"一站式"黑盒：没有 `render_and_upload()`，只有 `render.sh` 和 `upload.sh`。

### 2.2 文本流是通用接口
- 场景契约：`scenes/*/manifest.json`（JSON 文本）。
- 帧清单：`.agent/tmp/{scene}/frames/list.txt`（每行一个文件路径）。
- 时间码：`.agent/tmp/{scene}/timeline.csv`（帧号, 动作, 参数）。
- 渲染日志：`.agent/log/YYYYMMDD_HHMMSS_{task}.log`（纯文本）。
- Agent 无需解析二进制格式，`jq`、`awk`、`sed` 即可处理全部配置。

### 2.3 管道组合复杂任务
```bash
# 复杂动画的 UNIX 式表达
python -m manim scene.py --format png -o .agent/tmp/frames/ \
  | tee .agent/log/manim.log \
  && ffmpeg -f concat -i <(find .agent/tmp/frames -name "*.png" | sort | sed 's/^/file /') \
     -c:v libx264 -pix_fmt yuv420p out.mp4
```

### 2.4 透明性优于便利性
- 帧序列必须物理存在于文件系统，Agent 随时可用 `identify frame_120.png` 检查单帧。
- 引擎源码必须可被 `grep`：Agent 通过 `find $(python -c "import manim; print(manim.__path__[0]") -name "*.py" | xargs grep "class Circle"` 学习 API，而非查阅封闭文档。
- 所有命令执行日志写入 `.agent/log/`，Agent 出错时先 `tail -n 50 .agent/log/last_run.log`。
- 音频处理不隐藏为内部库调用，Agent 直接阅读 `pipeline/add_audio.sh` 中的 `ffmpeg` 命令。

### 2.5 优先使用工具而非机制
- 需要音频合成？调用 `ffmpeg -f lavfi` 生成测试音，不内建音频引擎。
- 需要公式渲染？调用 `pdflatex` 或 `mathjax-node-cli`，不内建排版系统。
- 需要缓存？使用文件时间戳和内容哈希判断（`bin/sourcemap-sync.py` 的 `content_hash`），不内建数据库。
- 需要视频剪辑？调用 `ffmpeg` 的 filtergraph，不内建时间轴编辑器。

---

## 3. 系统架构

### 3.1 目录结构（Agent 的"API 文档"）

```text
macode/
├── .agent/                  # Agent 工作区（可写，gitignored）
│   ├── tmp/                 # 临时帧、中间文件、原始输出
│   │   └── {scene_name}/
│   │       ├── frames/
│   │       │   ├── frame_0001.png
│   │       │   └── ...
│   │       ├── raw.mp4      # 无音频的原始渲染输出
│   │       ├── final.mp4    # 合成音频后的最终输出
│   │       └── render.log   # 该场景的完整渲染日志
│   ├── cache/               # 渲染缓存（按场景内容哈希）
│   └── log/                 # 全局命令执行日志
│
├── .githooks/               # Git hook 模板（版本化，setup 时安装到 .git/hooks/）
│   ├── pre-commit           #   提交前拦截：protected 文件 + scene 边界检查
│   └── pre-push             #   推送前全量安全扫描
│
├── engines/                 # 渲染引擎适配层（只读模板）
│   ├── manim/               #   ManimCE（CI/无头环境专用）
│   │   ├── src/
│   │   │   ├── templates/
│   │   │   ├── mobjects/
│   │   │   └── utils/
│   │   └── scripts/
│   │       ├── render.sh
│   │       └── inspect.sh
│   ├── manimgl/             #   ManimGL（交互式预览，默认 .py 引擎）
│   │   ├── src/
│   │   │   ├── components/    # ZoneScene, NarrativeScene（ManimGL 特有）
│   │   │   ├── templates/
│   │   │   └── utils/
│   │   └── scripts/
│   │       ├── render.sh
│   │       └── inspect.sh
│   └── motion_canvas/       #   Motion Canvas（.tsx 场景，WebGL）
│       ├── src/
│       │   ├── templates/
│       │   └── utils/
│       └── scripts/
│           ├── render.sh
│           └── inspect.sh
│
├── scenes/                  # 用户场景（Agent 主要工作区）
│   ├── 00_title/
│   │   ├── manifest.json      # 场景契约：引擎类型、时长、依赖
│   │   ├── scene.py           # 引擎实现（视图层）
│   │   └── assets/            # 图片、音频、字体、LaTeX 片段
│   ├── 01_intro/
│   │   ├── manifest.json
│   │   ├── scene.py
│   │   └── assets/
│   └── 02_fourier/
│       ├── manifest.json
│       ├── scene.tsx          # 若引擎为 motion_canvas
│       └── assets/
│
├── pipeline/                # 后处理管道（bash + ffmpeg 驱动）
│   ├── render.sh            # 读取 manifest，分发到引擎渲染脚本
│   ├── concat.sh            # 场景拼接（ffmpeg concat demuxer）
│   ├── add_audio.sh         # 音轨合成（ffmpeg amix / amerge）
│   ├── compress.sh          # 输出压缩（CRF / preset 控制）
│   └── ...                  #   fade.sh, preview.sh, validate-manifest.py, etc.
│
├── bin/                     # 全局工具脚本
│   ├── macode               # 主入口 CLI（子命令分派器）
│   ├── agent-run.sh         # Git 原子操作包装器
│   ├── install-hooks.sh     # 安装 .githooks/ 模板到 .git/hooks/
│   ├── setup.sh             # 项目初始化 — 用户版
│   ├── setup-dev.sh         # 项目初始化 — 开发版
│   ├── detect-hardware.sh   # GPU / OpenGL / CUDA 检测
│   ├── macode-dev.sh        # 引擎 dev 模式启动
│   ├── sourcemap-sync.py    # SOURCEMAP Markdown → JSON 同步
│   ├── api-gate.py          # 静态导入/API 黑名单检查
│   └── ...                  #   40+ 个独立 CLI 工具（见 §9 速查表）
│
└── project.yaml             # 全局配置：默认引擎、分辨率、fps、安全策略
```

### 3.2 三层解耦（可迁移性的基石）

```text
┌─────────────────────────────────────┐
│  Layer 3: Scene 描述 (manifest.json) │  ← 唯一不变层，引擎无关
├─────────────────────────────────────┤
│  Layer 2: Engine 适配 (engines/*)     │  ← 可替换：Manim ↔ Motion Canvas ↔ 未来引擎
├─────────────────────────────────────┤
│  Layer 1: 基础设施 (bash, ffmpeg, git)│  ← 绝对稳定，跨平台通用
└─────────────────────────────────────┘
```

**迁移示例**：将 Manim 场景迁移到 Motion Canvas：
1. Agent 读取 `manifest.json` 理解需求（时长、资产、依赖）。
2. Agent 用 `engines/motion_canvas/scripts/inspect.sh` 探索目标引擎能力。
3. Agent 用 `grep / find` 阅读目标引擎模板源码，理解映射关系。
4. Agent 生成新的 `scene.tsx`，修改 `manifest.json` 中的 `engine` 字段。
5. 重新运行 `pipeline/render.sh`，不修改任何管道脚本。

> **诚实的边界**：上述迁移对标准场景（纯几何、动画、文本）完全成立。但如果你使用了 ManimGL 特有的高阶抽象（如 §4.5 ZoneScene、§4.6 NarrativeScene），迁移需要重写这些语义层 —— 这是预期内的成本，而非架构失败。高阶抽象绑定到特定引擎是设计上的有意选择。

---

## 4. Host Agent 使用指南（直接调用 CLI）

MaCode 的每个工具都是**独立的 CLI**，可被 Host Agent 的标准 Bash 工具直接调用。无需进入任何自定义 shell。

### 4.0 Skill 工作流（可选增强）

MaCode 提供了结构化 skill 以加速工作流。引擎 API 参考（ManimCE / ManimGL / Motion Canvas）已通过符号链接集成到 `.agents/skills/` 命名空间，作为**默认增强路径**自动可用。

Skill 本质是一份带有 YAML frontmatter 的 Markdown 文档（`.agents/skills/macode-host-agent/SKILL.md`），任何 Host Agent 均可直接读取。

**位置**：`.agents/skills/macode-host-agent/SKILL.md`

**Skill 内容**（按需深入，渐进式披露）：

| 层级 | 文件 | 内容 | 何时查阅 |
|------|------|------|----------|
| 第一层 | `SKILL.md` | 触发条件 + 核心指令摘要 | 判断 skill 是否适用 |
| 第二层 | `workflows/` | 工作流模板（单场景渲染、检查-修复循环） | 执行具体任务时 |
| 第三层 | `prompts/system-prompt.md` | 完整的 Agent 角色定义和安全约束 | 需要完整上下文时 |
| 第四层 | `references/` | API 速查表、退出码表、**引擎参考索引** | 遇到特定问题时 |
| 第五层 | `examples/` | 典型场景的完整 prompt 示例 | 需要复用模式时 |
| **引擎参考** | `.agents/skills/{engine}/` | ManimCE / ManimGL / Motion Canvas API 文档 | 编写场景源码时 |

**可用引擎参考 Skill**（按 manifest `engine` 字段自动选择）：

| Skill | 路径 | 内容 | 适用 engine |
|-------|------|------|-------------|
| `manimce-best-practices` | `.agents/skills/manimce-best-practices/` | 22 个 rules（Scene、Mobject、Create、MathTex、Axes、3D...） | `manim` |
| `manimgl-best-practices` | `.agents/skills/manimgl-best-practices/` | 15 个 rules（InteractiveScene、ShowCreation、Tex、t2c、frame.reorient...） | `manimgl` |
| `motion-canvas` | `.agents/skills/motion-canvas/` | 18 个 references（Signal、Tween、Layout、Txt、Latex...） | `motion_canvas` |
| `manim-composer` | `.agents/skills/manim-composer/` | 视频规划、3b1b 叙事结构、场景模板 | 任何引擎（规划阶段） |

**使用建议**：
1. 先阅读本文件（`AGENTS.md`）理解整体架构和约束
2. 执行具体任务时，读取 skill 文件获取结构化工作流
3. 编写场景源码时，按 `manifest.json` 的 `engine` 字段查阅对应引擎参考 skill
4. 遇到 skill 未覆盖的边界情况时，回到本文件查阅深层设计原理

### 4.1 工具发现

```bash
# 查看项目配置
cat project.yaml

# 查看硬件画像（JSON，机器可读）
cat .agent/hardware_profile.json | jq .

# 查看可用引擎
ls engines/

# 查看引擎配置
cat engines/manim/engine.conf
```

### 4.2 场景编写 → 渲染（标准工作流）

```bash
# 1. 编写场景源码和契约
#    scenes/02_fourier/manifest.json  +  scenes/02_fourier/scene.py

# 2. 渲染（自动通过 api-gate + 缓存检查）
pipeline/render.sh scenes/02_fourier/
# 输出: .agent/tmp/02_fourier/final.mp4

# 3. 若渲染失败，查看日志
tail -50 .agent/log/*.log

# 4. 预览
pipeline/preview.sh .agent/tmp/02_fourier/final.mp4
```

#### Motion Canvas 场景渲染（Harness 2.0）

Motion Canvas 场景通过 `manifest.json` 中的 `"engine": "motion_canvas"` 自动路由到 Harness 2.0：

```bash
# 完整渲染（自动启动 dev server → 抓帧 → 清理）
macode render scenes/02_shader_mc/
# 或显式传参
macode render scenes/02_shader_mc/ --fps 30 --duration 3 --width 1920 --height 1080

# 分步控制（开发调试）
macode mc serve scenes/02_shader_mc/        # 启动 dev server，输出随机端口
macode mc stop scenes/02_shader_mc/         # 停止 dev server

# 单帧截图（snapshot.mjs 为 render.mjs 薄封装，或直接）
node engines/motion_canvas/scripts/render.mjs --snapshot \
  scenes/02_shader_mc/scene.tsx snapshot.png 1.5 30 1920 1080
```

**MC 场景 manifest 示例**：
```json
{
  "engine": "motion_canvas",
  "duration": 3,
  "fps": 30,
  "resolution": [1920, 1080],
  "shaders": ["lygia_circle_heatmap"]
}
```
`shaders` 列表中的 Layer 2 素材会在渲染前自动预渲染为 PNG 帧序列，供 `ShaderFrame` 节点消费。

**Harness 2.0 CLI（Sprint 3）**：`engines/motion_canvas/scripts/render.mjs` 合并了原 `serve.mjs` / `stop.mjs` / `playwright-render.mjs`：批量渲染时在同一进程内拉起 Vite、Playwright 抓帧、再杀掉 dev server；`macode mc serve|stop` 映射为 `render.mjs --serve-only` 与 `render.mjs --stop`。不再使用独立的 Browser Pool 与 `server-guardian.mjs`。

### 4.3 批量渲染与后处理

```bash
# 批量渲染所有场景
bin/render-all.sh

# 多场景拼接
pipeline/concat.sh scenes/*/output/final.mp4 output/lecture.mp4

# 音频合成
pipeline/add_audio.sh output/lecture.mp4 assets/bgm.mp3 output/final.mp4

# 压缩（社交媒体版本）
pipeline/compress.sh output/final.mp4 output/final_small.mp4
```

### 4.4 Composite Scene System（模块化场景合成）

将复杂场景拆分为独立 Segment，分别渲染后合成。支持转场效果、背景音乐、跨 Segment 参数注入。

**创建 composite 场景**：
```bash
# 从模板创建（支持 --engine manim / motion_canvas）
macode composite init scenes/09_lecture --template intro-main-outro
# → 生成 shots/00_intro, shots/01_main, shots/02_outro + 顶层 manifest.json

# 添加 segment（自动检测引擎类型）
macode composite add-segment scenes/09_lecture bonus --after main
```

**Composite manifest 契约**：
```json
{
  "type": "composite",
  "segments": [
    {"id": "intro", "scene_dir": "shots/00_intro",
     "transition": {"type": "fade", "duration": 0.3}},
    {"id": "main", "scene_dir": "shots/01_main",
     "transition": {"type": "wipeleft", "duration": 0.5}},
    {"id": "outro", "scene_dir": "shots/02_outro"}
  ],
  "audio": {
    "tracks": [{"file": "assets/bg.mp3", "loop": true, "volume": 0.2}]
  },
  "params": {"theme_color": "#1E90FF", "title_text": "讲座标题"}
}
```

**参数注入**：Segment 源码通过环境变量读取 composite 参数：
- **Manim**: `json.load(open(os.environ["MACODE_PARAMS_JSON"]))`
- **Motion Canvas**: `(window as any).__MACODE_PARAMS`（由 `render.mjs` 自动注入）

**渲染**：
```bash
# 自动并行渲染独立 segments，缓存命中跳过，最后 concat/xfade 合成
pipeline/render.sh scenes/09_lecture/
# 或
macode composite render scenes/09_lecture
```

**双轨架构**：
| 模式 | type | 特点 |
|------|------|------|
| 分轨合成 | `composite` | 独立渲染 + ffmpeg xfade，可并行，状态不连续 |
| 统一渲染 | `composite-unified` | 单 Scene 实例顺序执行，状态连续 |

> **统一渲染路由**：`composite-unified` 不通过独立 CLI 入口调用。运行 `macode composite render <scene_dir>` 或 `pipeline/render.sh <scene_dir>` 时，`render.sh` 自动读取 `manifest.json` 的 `type` 字段并分发到 `pipeline/composite-unified-render.py`。

### 4.5 Zone/Region Constraint System（ManimGL + ManimCE）

> **引擎支持声明**：ZoneScene 布局系统已在 **ManimGL** 和 **ManimCE** 中实现（`engines/manimgl/src/components/zoned_scene.py` 和 `engines/manim/src/components/zoned_scene.py`）。Motion Canvas 无等价实现 —— 其声明式 React 节点模型与命令式 zone placement 没有自然映射。

声明式空间约束系统，确保数学对象在场景中按语义区域放置，避免视觉混乱。

**核心组件**：
- **`ZoneScene`**（`engines/manimgl/src/components/zoned_scene.py`）：基类，提供 `place(mobj, zone_name)`、`place_in_grid(...)`、`zone_center(...)` 等 API。子类通过 `LAYOUT_PROFILE` 选择布局模板。
- **`layout_geometry.py`**：纯几何计算（像素 ↔ Manim 单位转换、zone 边界、对齐点计算），无引擎依赖。
- **`layout_validator.py`**：约束验证（max_objects、allowed_types、primary_zone 非空检查）。

**典型布局模板**（`engines/manimgl/src/templates/layouts/`）：
- `lecture_3zones`：title / main_visual / caption
- `lecture_2zones`：title / content

**使用示例**：
```python
from components.zoned_scene import ZoneScene

class MyScene(ZoneScene):
    LAYOUT_PROFILE = "lecture_3zones"

    def construct(self):
        self.place(Text("极限的定义"), "title")
        self.place(Axes(x_range=[-3, 3]), "main_visual")
        self.place(MathTex(r"\lim_{x \to a} f(x) = L"), "caption")
        self.validate_primary_zone()  # 确保主视觉区有非文本对象
```

### 4.6 Narrative Mode Library（ManimGL + ManimCE）

> **引擎支持声明**：NarrativeScene 已在 **ManimGL** 和 **ManimCE** 中实现（`engines/manimgl/src/components/narrative_scene.py` 和 `engines/manim/src/components/narrative_scene.py`）。动画原语自动映射到各引擎的正确名称（ManimGL 的 `ShowCreation` → ManimCE 的 `Create`）。Motion Canvas 无等价实现。

叙事模板驱动的场景编排，将数学讲解抽象为可复用的叙事阶段（stage）。

**核心组件**：
- **`NarrativeScene`**（`engines/manimgl/src/components/narrative_scene.py`）：继承 `ZoneScene`，提供 `stage(stage_id, *mobjects)` 方法。自动验证阶段顺序、选择动画原语、检查主视觉区首次出现时间。
- **Narrative Templates**（`engines/manimgl/src/templates/narratives/`）：
  - `definition_reveal`：statement → visual → annotation → example
  - `build_up_payoff`：setup → tension → climax → resolution
  - `wrong_to_right`：wrong_attempt → correction → explanation
- **`narrative_validator.py`**：阶段顺序验证（`must_be_first`、`requires`）、主视觉区超时检查。

**使用示例**：
```python
from components.narrative_scene import NarrativeScene

class MyScene(NarrativeScene):
    LAYOUT_PROFILE = "lecture_3zones"
    NARRATIVE_PROFILE = "definition_reveal"

    def construct(self):
        self.stage("statement", Text("极限的定义"))
        self.stage("visual", NumberLine(x_range=[-5, 5]))
        self.stage("annotation", MathTex(r"\lim_{x\to a} f(x) = L"))
        self.stage("example", Circle())
```

### 4.7 SOURCEMAP 协议 —— Agent 的安全地图

`engines/{name}/sourcemap.json` 是黑白名单与安全元数据的 **唯一机器真源**。同目录下的 `SOURCEMAP.md` 是由 `bin/sourcemap-sync.py` **从 JSON 生成**的人类可读视图；若二者不一致，`sourcemap-sync.py --check` 会报错。

它不是给使用者 Agent随意编辑的草稿，而是 **Harness 用来约束和引导 Agent 的协议**（人类维护者修改 JSON → 再生 MD）。

**核心原则**：
- **使用者 Agent 只读** SOURCEMAP，通过 `macode inspect` 查询 API
- **开发者 Agent 读写** SOURCEMAP，负责维护引擎适配层
- Harness 在启动时将它注入 Agent 的**工作记忆**，在编码时用它做**审查门**，在出错时用它做**诊断地图**

**Agent 工作流中的 SOURCEMAP**：

```bash
# 1. 启动时自动加载（macode CLI / setup）
python3 bin/sourcemap-sync.py --all
# → 校验 engines/{engine}/sourcemap.json（jsonschema）
# → 写回同源 SOURCEMAP.md + .agent/context/{engine}_sourcemap.json 等副本

# 2. 编码前查询 API
macode inspect --grep "NumberLine\|Axes\|MathTex"
# → 查询 SOURCEMAP WHITELIST，确认 API 存在且安全

# 3. 渲染前自动审查（pipeline/render.sh 内置）
pipeline/render.sh scenes/02_demo/
# → api-gate.py 对照 engines/<engine>/sourcemap.json BLACKLIST（与 manifest.engine 对齐）
# → 若发现 "import manimlib" → 立即阻断，提示修复

# 4. 出错时定向诊断（engines/*/scripts/render.sh 内置）
# → 日志解析器扫描错误关键词
# → 匹配 BLACKLIST 条目 → "你踩了 DEPRECATED_GL，修复方案是 X"
```

**自动化维护工具链**（开发者关注）：

| 工具 | 职责 | 何时运行 |
|------|------|---------|
| `sourcemap-version-check.py` | 检测引擎版本漂移 | `setup.sh` 自动调用；`macode status` 显示 |
| `sourcemap-scan-api.py` | 扫描未覆盖的公共 API / 适配层文件 | 引擎升级后手动运行，生成建议清单 |
| `sourcemap-sync.py` | JSON（真源）→ SOURCEMAP.md + `.agent/context` | `setup.sh` 自动调用；改 JSON 后手动 `sync` |
| `engines/*/scripts/validate_sourcemap.sh` | WHITELIST/BLACKLIST 路径存在性 | 改路径后或与 CI 对齐时运行 |

薄封装：`macode sourcemap validate|generate-md|scan-api|version-check`（见 `bin/macode`）。

```bash
# 快速健康检查（也见 macode sourcemap version-check）
python3 bin/sourcemap-version-check.py --all
# → 报告 engines/*/sourcemap.json version 字段与已安装引擎是否一致

# 扫描 API 覆盖缺口
python3 bin/sourcemap-scan-api.py --all
# → 列出适配层新文件、引擎公共类/函数中未在 WHITELIST 注册的项目
# → 开发者审核后选择性加入 engines/*/sourcemap.json（再 generate-md）
```

**SOURCEMAP 维护触发条件**：
- 引擎版本升级（`pip install --upgrade manim` / `npm update`）→ 先运行 `version-check`，再运行 `scan-api`
- Agent 误入陷阱（复盘后补入 BLACKLIST）
- 适配层新增代码（`engines/{name}/src/` 下新增文件）→ `scan-api` 会检测到
- 扩展计划变更（EXTENSION 中的 TODO → DONE/WONTFIX）

**验证**：修改 **sourcemap.json**（真源）后：
```bash
python3 bin/sourcemap-sync.py --check {name}                 # MD 与 JSON 一致
bash engines/{name}/scripts/validate_sourcemap.sh            # 路径存在性
python3 bin/sourcemap-sync.py {name}                       # 再生 SOURCEMAP.md / .agent/context
python3 bin/sourcemap-version-check.py {name}                # 版本匹配
```
或 `macode sourcemap validate {name}`（含 `--check` + `validate_sourcemap.sh`）。

### 4.8 Layout Compiler 工作流

MaCode 提供可选的**两阶段编译器**，将"内容清单 → 布局配置 → 场景源码"的重复劳动自动化。Agent 在"内容明确、结构标准化"时推荐使用 Compiler；在"需要创意布局、非标准结构"时仍应手写 `scene.py`。

**两阶段编译**：
```bash
# Phase 1: 内容 → 布局（确定性分配 + 约束验证）
bin/layout-compile.py scenes/{name}/content_manifest.json \
  --output scenes/{name}/layout_config.yaml

# Phase 2: 布局 → 场景源码（模板填充）
bin/scene-compile.py scenes/{name}/layout_config.yaml \
  --engine {manim,manimgl,motion_canvas} \
  --output scenes/{name}/scene.py
```

**何时使用 Compiler**：
- 使用 `lecture_3zones` + `definition_reveal` / `build_up_payoff` / `wrong_to_right` 等标准模板
- 内容以文本、公式、基础图元（Circle/Axes/NumberLine 等）为主
- 需要快速迭代内容而不想手动调整坐标

**何时手写 scene.py**：
- 非标准布局（不使用预定义 zone 模板）
- 复杂动画序列、自定义过渡、交互式内容
- 内容与结构同步探索的阶段

**约束验证**：`layout-compile.py` 在输出前自动验证：
- 每个 zone 的对象数 ≤ `max_objects`
- 总文本字符数 ≤ `max_total_text_chars`
- primary zone 至少包含一个 visual

验证失败时输出明确的错误信息和修复建议，exit code 1。

**未映射图元处理**：`scene-compile.py` 遇到当前引擎无映射的 primitive 时，输出 `TODO` 注释而非失败。Agent 需手工补充该部分代码。

完整规范见 `.agents/skills/layout-compiler/SKILL.md`。

---

## 5. 安全模型：四层防御（Harness 2.0 Security）

MaCode 采用**纵深防御**：从提示词到运行时到提交拦截到权限隔离，每层独立生效，任何一层被绕过仍有下一层保护。

### 5.1 Layer 0 — 提示词约束（Prompt Guardrails）

各 AI 工具的配置文件分散在仓库根目录，无中央生成器：

```
.claude/settings.local.json     # Claude Code 配置
.cursorrules                    # Cursor 配置
.github/copilot-instructions.md # GitHub Copilot 配置
.windsurf/rules.md              # Windsurf 配置
.aider.conf.yml                 # Aider 配置
```

> 注：早期设计中有 `.agents/security/prompt-policy.yml` 作为统一策略源，但实际维护中改为各工具独立配置，避免单点变更影响所有 IDE。

核心约束：
- **Allowed**: `scenes/*`, `assets/*` 读写
- **Forbidden**: `engines/*`, `bin/*`, `pipeline/*`, `project.yaml` 修改
- **Never**: `subprocess`, `os.system`, `socket`, `requests` in scene code

### 5.2 Layer 1 — 运行时强制（Runtime Enforcement）

薄分发器 `bin/security-run.sh` 并行调用四个独立检查器：

```bash
# 单场景完整安全检查
bin/security-run.sh scenes/01_test/

# 独立调用（调试用）
bin/api-gate.py        scenes/01_test/scene.py engines/manim/sourcemap.json --engine manim
bin/sandbox-check.py   scenes/01_test/scene.py
bin/primitive-gate.py  scenes/01_test/
bin/fs-guard.py        scenes/01_test/
```

| 检查器 | 职责 | 检测内容 |
|--------|------|---------|
| `api-gate.py` | 导入/API 黑名单 | BLACKLIST 导入、SOURCEMAP 违规 |
| `sandbox-check.py` | 危险 Python 调用 | `subprocess`, `os.system`, `socket`, `requests`, `shutil.rmtree` |
| `primitive-gate.py` | 原语写入检测 | 手写 GLSL、raw LaTeX、手写 ffmpeg filtergraph、 forbidden 文件类型 |
| `fs-guard.py` | 文件系统边界 | 场景目录是否越界（必须位于 `scenes/` / `assets/` / `output/` / `.agent/`） |

**四问法验证**：每个检查器都是只读的纯决策工具，互不依赖，可独立运行。

### 5.3 Layer 2 — 提交拦截（Commit Interception）

Hooks 以版本化模板形式存在于 `.githooks/`，由 `bin/install-hooks.sh` 在 setup 时复制到 `.git/hooks/`：

```bash
# 安装/更新 hooks（首次 setup 或模板变更后运行）
bin/install-hooks.sh

# 验证 hooks 已安装且为最新
bin/install-hooks.sh --check
```

激活后的 hooks：
```bash
.git/hooks/pre-commit   # 拦截 protected 文件修改 + scene 目录边界检查
.git/hooks/pre-push     # 推送前全量安全扫描
```

拦截规则：
- `engines/`、`bin/`、`pipeline/` 任何修改 → **拒绝**
- `project.yaml`、`requirements.txt`、`package.json` 修改 → **拒绝**
- Scene 目录越界 → **拒绝**
- Bypass: `git commit --no-verify`（人类基础设施维护时使用）

> **注意**：`.githooks/` 目录本身不受 pre-commit 保护，因此 hooks 模板可以被正常更新而无需 `--no-verify`。

### 5.4 Layer 3 — 基础设施隔离（Infrastructure Isolation）

**根本解决方案：让 Agent 物理上写不了。**

```bash
# 基础设施目录只读（符号性，真正的强制在 fs-guard + git hooks）
chmod -R go-w engines/ bin/ pipeline/ tests/ docs/
```

**原语隔离矩阵**：

| 原语 | 隔离措施 | 替代方案 |
|------|---------|---------|
| GLSL | `assets/shaders/` 只读 + Effect Registry | 声明效果名称，编译器生成 |
| Raw LaTeX | SYNTAX_REDIRECTS 拦截 | `natural_math.py` API |
| ffmpeg filtergraph | SYNTAX_REDIRECTS 拦截 | `ffmpeg_builder.py` API |
| 引擎配置 | `engine.conf` / `project.yaml` 只读 | `macode` CLI 修改 |
| socket/http | SANDBOX_PATTERNS 拦截 | `macode-run` 统一 IPC |

### 5.5 Security Guardian Subagent（可选增强）

独立进程，实时监控文件系统：

```bash
# 后台守护进程
python3 .agents/skills/security-guardian/bin/security-guardian.py --daemon

# 审计日志
jq . .agent/security/audit.log
```

职责：检测运行时绕过尝试（如 Agent 通过 `open()` 直接写 `engines/`）。

注意：Guardian 是可选的 1% 增强，Layer 1-3 已覆盖 99% 威胁。

### 5.6 资源熔断（render-scene.py 内置）

```bash
# 读取 project.yaml，无需 Host Agent 干预
# - 渲染超时：600s  （由 engines/*/scripts/render.sh 强制执行）
# - 全局并发上限：max_concurrent_scenes  （由 bin/render-all.sh / pipeline/composite-render.py 强制执行）
#
# 以下限制在 project.yaml 中声明，但当前未自动化强制执行：
# - 帧数上限：10000
# - 磁盘上限：50GB
#   （依赖 Host Agent 自觉遵守，或后续通过 render-scene.py 内置熔断实现）
```


---

## 6. 引擎选型策略

项目级默认引擎以仓库根目录 `project.yaml` 中的 `defaults.engine` 为唯一真源。The canonical default engine is `defaults.engine` in `project.yaml` at the repository root.

### 6.1 ManimGL（.py 场景）

- **理由**：3b1b 实际使用的引擎，OpenGL 实时预览，开发迭代效率最高。Agent 写 `from manimlib import *` 即可获得完整的数学动画抽象。
- **定位**：适合 Agent 在本地快速迭代 `.py` 场景。
- **约束**：必须通过 `engines/manimgl/scripts/render.sh` / `dev.sh` 调用。

### 6.2 Motion Canvas（.tsx 场景）

- **理由**：浏览器 WebGL 热重载，Shader 实时编译，数据可视化/UI 布局能力强。
- **定位**：适合声明式 `.tsx` 场景；Shader 特效、数据可视化、交互式内容的首选。
- **约束**：通过 Harness 2.0 — `engines/motion_canvas/scripts/render.mjs`（统一抓帧与可选 dev server）。`bin/macode render` 自动识别 `manifest.json` 的 `engine: motion_canvas` 并路由。
- **架构**：Layer 2 shader 素材（LYGIA）由 `ShaderFrame.tsx` 通过浏览器 WebGL2 实时编译渲染；Playwright 在 Chromium 中抓帧输出 `frame_%04d.png`。

### 6.3 生产引擎：ManimCE（CI/无头环境专用）

- **理由**：纯 CPU 确定性输出，无 GPU 也能运行，跨平台字体渲染一致。
- **定位**：**CI / 最终交付 / 无头环境** 专用。Agent 快速迭代阶段**不推荐**使用。
- **约束**：`mode: batch`，无实时预览能力。当前通过 `watch + 低分辨率重渲染` 模拟 dev 体验，但这是 workaround 而非原生能力。

### 6.4 引擎自动推断

```bash
# macode-dev.sh / dry-run.py / render.sh 的默认回退逻辑
manifest 无 engine 字段时：
  .tsx 文件存在 → motion_canvas
  .py  文件存在 → manimgl
  其他           → manimgl
```

### 6.5 明确不选
- **Remotion（作为主引擎）**：通用视频工具，无内置数学对象抽象。仅适合"最终拼接层"。
- **SoX（音频处理）**：Windows 兼容性差。所有音频由 `ffmpeg` 统一处理。

### 6.6 WSL2 运行环境调优

MaCode 的推荐 Windows 运行方式是 **WSL2**（而非原生 Windows）。WSL2 提供完整的 Linux 内核 + NVIDIA D3D12 GPU passthrough，性能损失通常 <10%。

**自动检测与修复**：
```bash
bin/check-wsl2.sh          # 检测 WSL2 配置问题
bin/check-wsl2.sh --json   # 机器可读输出
```
`setup.sh` 会自动调用此脚本。

**关键约束**：

| 项目 | 要求 | 后果 |
|------|------|------|
| 项目位置 | 必须放在 WSL2 **原生文件系统** (`~/MaCode`) | `/mnt/c` 上的 9p/DRVS 性能差 10-50 倍，且 inotify 失效 |
| GPU 驱动 | 安装 [WSL2 NVIDIA 驱动](https://developer.nvidia.com/cuda/wsl) | 否则 OpenGL 回退到 llvmpipe（纯 CPU，极慢） |
| `vm.max_map_count` | `>= 262144` | Chromium/Playwright 启动失败 |
| `fs.inotify.max_user_watches` | `>= 524288` | 大项目文件监听断连 |
| `/dev/shm` | `>= 1GB` | Chromium OOM 崩溃 |
| WSLg | 更新到最新 WSL2 | ManimGL 交互预览需要 GUI 支持 |

**`.wslconfig` 建议**（Windows 用户目录 `%USERPROFILE%\.wslconfig`）：
```ini
[wsl2]
memory=12GB
processors=8
swap=4GB
localhostForwarding=true
guiApplications=true
kernelCommandLine=tmpfs.size=2G
```

**`.wslconfig` 生效后**：
```powershell
wsl --shutdown   # 完全关闭 WSL2 VM
wsl              # 重新启动
```

**GPU 加速状态确认**：
```bash
bash bin/detect-hardware.sh
cat .agent/hardware_profile.json | jq '.opengl.renderer'
# 期望输出: "D3D12 (NVIDIA ...)"
# 如果输出 "llvmpipe": 驱动未正确安装
```

---

## 7. 文件命名与接口约定

### 7.1 场景目录命名
```text
scenes/
├── 00_title/          # 序号前缀保证管道拼接顺序
├── 01_intro/
├── 02_fourier_series/
└── 03_epilogue/
```

### 7.2 中间产物命名
```text
.agent/tmp/{scene_name}/
├── frames/
│   ├── frame_0001.png
│   └── ...
├── raw.mp4            # 无音频的原始渲染输出
├── final.mp4          # 合成音频后的最终输出
└── render.log         # 该场景的完整渲染日志
```

### 7.3 日志规范
所有脚本必须将 stderr + stdout 追加到 `.agent/log/YYYYMMDD_HHMMSS_{script_name}.log`，Agent 调试时通过 `tail` 读取。

---

## 8. 反模式（Agent 禁止做的事）

1. **不要内建 IDE**：Agent 不需要"智能提示"，它需要 `grep` 和 `find`。
2. **不要抽象过度**：不要为 Manim 和 Motion Canvas 创建统一的 Python/TypeScript SDK。统一层只在 `manifest.json` 和 `pipeline/*.sh` 中存在。
3. **不要隐藏中间状态**：禁止将帧序列输出为内存流或临时删除。Agent 必须能 `ls` 看到每一帧。
4. **不要动态下载依赖**：Agent 禁止执行 `pip install` 或 `npm install`。依赖必须在项目初始化时固化（`requirements.txt`、`package-lock.json`、Docker 镜像）。
5. **不要假设引擎版本**：Agent 必须通过 `engines/*/scripts/inspect.sh` 查询能力，不硬编码 API。
6. **不要引入额外音频工具**：所有音频处理由 `ffmpeg` 完成，禁止调用 `sox`、`audacity` 或其他音频处理软件。
7. **不要绕过 SOURCEMAP 审查**：禁止直接修改 `engines/{name}/SOURCEMAP.md`。禁止在 `api-gate.py` 拦截后强行渲染。禁止 `grep -r` 整个引擎源码树 —— 用 `macode inspect` 按图索骥。
8. **不要忽略 SOURCEMAP 诊断**：渲染失败时先读日志中的定向诊断建议，不盲目重试。错误信息指向 BLACKLIST 条目时，按提示修复而非绕过。

---

## 9. CLI 工具速查表（Host Agent 参考）

| 工具 | 用途 | 典型调用 | 输出 |
|------|------|----------|------|
| `pipeline/render.sh <scene_dir>` | 渲染场景 | `pipeline/render.sh scenes/01_test/` | `.agent/tmp/{scene}/final.mp4` |
| `bin/render-all.sh` | 批量渲染 | `bin/render-all.sh --parallel 4` | 所有场景的 `final.mp4` |
| `bin/macode status` | 项目状态 | `bin/macode status` | 文本摘要 |
| `bin/macode check <scene_dir>` | 静态 + 帧检查 | `macode check scenes/01_test --static` | 检查报告 JSON |
| `bin/macode cleanup [--dry-run]` | 清理 dead PID（stalled）与可选日志裁剪 | `macode cleanup --dry-run` | 清理报告 |
| `bin/install-hooks.sh [--check]` | 安装/检查 git hooks | `bin/install-hooks.sh --check` | 安装报告或状态检查 |
| `bin/macode dry-run <scene_file>` | 预渲染验证（语法、导入、LaTeX） | `macode dry-run scenes/01_test/scene.py` | 通过/失败 + 问题列表 |
| `bin/calc-preview-duration.py <manifest>` | 计算预览时长 | `calc-preview-duration.py scenes/01_test/manifest.json` | 预览秒数（如 `3.0`） |
| `bin/patch-manifest.py <manifest>` | 原子修改 manifest | `patch-manifest.py m.json --duration 3 --fps 10` | 原子写回，支持 `--backup` / `--restore` |
| `bin/watch-file.sh <file>` | 轮询监听文件变化 | `watch-file.sh scene.py --exec "echo changed"` | 变化时执行命令 |
| `bin/macode inspect --grep <re>` | 查询 API | `bin/macode inspect --grep "Circle\|MathTex"` | 匹配的 WHITELIST 条目 |
| `cat .agents/skills/{engine}/SKILL.md` | 引擎 API 参考 | `cat .agents/skills/manimce-best-practices/SKILL.md` | 完整引擎 API 文档 |
| `bin/api-gate.py <scene.py> engines/<engine>/sourcemap.json [--engine]` | 代码审查 | `bin/api-gate.py scenes/01_test/scene.py engines/manim/sourcemap.json --engine manim` | 退出码 0/1（违规）/2（参数或 JSON）
| `bin/sourcemap-version-check.py` | SOURCEMAP 版本漂移检测 | `python3 bin/sourcemap-version-check.py --all` | 每个引擎的匹配状态 |
| `bin/sourcemap-scan-api.py` | 扫描未覆盖的公共 API | `python3 bin/sourcemap-scan-api.py --all` | 建议加入 WHITELIST 的候选 |
| `bin/sourcemap-sync.py [engine] \| --all \| --check` | JSON ↔ 视图与 agent 上下文 | `python3 bin/sourcemap-sync.py --all` | `.agent/context/*` + 各引擎 `SOURCEMAP.md`
| `bin/sourcemap-read <engine> <section>` | 查询 JSON sourcemap | `sourcemap-read manim whitelist --level P0` | 筛选后的条目列表 |
| `bin/detect-hardware.sh` | 硬件检测 | `bash bin/detect-hardware.sh` | `.agent/hardware_profile.json` |
| `bin/select-backend.sh` | 后端选择 | `bash bin/select-backend.sh` | `gpu` / `d3d12` / `cpu` / `headless` |
| `pipeline/concat.sh <frames_dir> <out.mp4> [fps]` | 帧序列编码 | `pipeline/concat.sh .agent/tmp/01_test/frames/ out.mp4 30` | MP4 文件 |
| `pipeline/add_audio.sh <video> <audio> <out>` | 音轨合成 | `pipeline/add_audio.sh out.mp4 bgm.mp3 final.mp4` | MP4 文件 |
| `pipeline/compress.sh <in> <out>` | 视频压缩 | `pipeline/compress.sh final.mp4 small.mp4` | MP4 文件 |
| `pipeline/preview.sh <mp4>` | 快速预览 | `pipeline/preview.sh final.mp4` | 降分辨率预览文件 |
| `bin/macode-dev.sh <scene_dir> [opts]` | 启动引擎 dev 模式 | `macode-dev.sh scenes/01_test` | 引擎特定的实时预览/快照 |
| `engines/*/scripts/inspect.sh` | 引擎能力查询 | `engines/manim/scripts/inspect.sh` | 可用模板/API 列表 |
| `macode mc serve <scene_dir>` | 启动 MC dev server | `macode mc serve scenes/02_shader_mc/` | 端口输出到 stdout |
| `macode mc stop <scene_dir>` | 停止 MC dev server | `macode mc stop scenes/02_shader_mc/` | SIGTERM → SIGKILL |
| `macode shader list` | 列出 Layer 2 shader 素材 | `macode shader list` | 注册表中的所有素材 |
| `macode shader render <dir>` | 预渲染 shader 到 PNG | `macode shader render assets/shaders/lygia_fire/` | 输出到 `shader_dir/frames/` |
| `node bin/dashboard-server.mjs` | 启动实时仪表盘 | `node bin/dashboard-server.mjs --port 3000` | 浏览器/CLI 消费 `.agent/progress/*.jsonl` |

### 退出码约定

| 退出码 | 含义 |
|--------|------|
| 0 | 成功 |
| 1 | 通用错误 / api-gate 拦截 |
| 124 | 渲染超时（timeout 触发）|

### Host Agent 工作流建议

1. 读取 `project.yaml` 了解配置
2. 读取目标 `scenes/*/manifest.json` 理解需求
3. 使用 `macode inspect --grep <keyword>` 或 `engines/*/scripts/inspect.sh` 查询 API
   - **补充**：按 `manifest.json` 的 `engine` 字段查阅 `.agents/skills/{engine}/` 下的参考 skill，获取详细用法和示例
4. 编写场景源码（`scene.py` + `manifest.json`）
5. 可选：预检 `bin/api-gate.py` 确认无违规导入
6. 调用 `pipeline/render.sh <scene_dir>` 渲染
7. 若失败：`tail .agent/log/*.log` 查看诊断
8. 后处理：`pipeline/*.sh` 拼接 / 音频 / 压缩

---

## 10. 实时仪表盘（人类监控，Agent 零感知）

MaCode 仪表盘是**文件系统的可选可视化皮肤**，不是 Agent 的必需通信管道。

### 架构原则

| 原则 | 实现 |
|------|------|
| **文本流是唯一真相源** | Agent 只写 `.agent/progress/*.jsonl`，不感知仪表盘 |
| **仪表盘只读文件系统** | `dashboard-server.mjs` 不写入任何状态，重启后重建视图 |
| **仪表盘是可选消费者** | 人类可用 `tail -f` 也可用浏览器，Agent 永远 `cat` |
| **仪表盘暴露底层路径** | 每个 UI 元素都可追溯到具体文件路径 |

### 启动仪表盘

```bash
# 独立进程，Agent 完全不感知
node bin/dashboard-server.mjs --port 3000 &

# 浏览器打开（人类监控）
open http://localhost:3000/

# CLI 消费（同样有效）
curl -s http://localhost:3000/api/state | jq '.scenes[] | select(.status == "running")'
```

### 进度文本流

```bash
# Agent 渲染时自动写入
.agent/progress/05_new.jsonl
# → {"timestamp":"...","phase":"capture","status":"running","progress":0.67,"frames_rendered":60,"frames_total":90}

# 人类用 UNIX 工具处理
tail -f .agent/progress/*.jsonl | jq '.phase'
```

### API 端点

| 端点 | 说明 |
|------|------|
| `GET /` | HTML 仪表盘页面 |
| `GET /api/state` | 当前所有场景状态 JSON |
| `GET /api/events` | SSE 实时推送流 |

---

## 11. 人类介入协议

MaCode 提供文件系统信号机制，人类可随时监控和介入。

信号分为**全局**（影响所有 scene）和 **per-scene**（只影响特定 scene）：

```text
.agent/signals/
├── global/
│   ├── pause              # 全局暂停所有 Agent
│   └── abort              # 全局中止所有 Agent
├── human_override.json    # 全局覆盖决策
└── per-scene/
    └── {scene_name}/
        ├── pause          # 只暂停该 scene
        ├── abort          # 只中止该 scene
        ├── review_needed  # 该 scene 等待审核
        ├── reject         # 该 scene 被驳回
        └── human_override.json  # 该 scene 的覆盖决策
```

### Host Agent 义务（每次执行动作前）
1. 检查 per-scene 信号（`.agent/signals/per-scene/{scene}/pause|abort`）— 存在则针对该 scene 暂停/退出
2. 回退检查全局信号（`.agent/signals/global/pause|abort`）— 存在则全部暂停/退出
3. 检查 `.agent/signals/human_override.json` — 存在则遵守覆盖决策
4. 检查 per-scene `review_needed` — 存在则该 scene 停止等待审核

使用 `bin/signal-check.py` 统一查询：
```bash
# 查询所有信号（全局 + 全部 scene）
python3 bin/signal-check.py

# 只查询全局信号
python3 bin/signal-check.py --global-only

# 查询特定 scene 的信号
python3 bin/signal-check.py --scene 01_test
```

### Host Agent 权利
1. 渲染完成后自动运行 check，生成报告
2. 生成 HTML 画面报告到 `.agent/reports/`
3. 发现严重问题时创建 `review_needed` 请求人类审核
4. 读取 `@human:` 注释并优先处理

### 人类权利
1. 随时 `touch .agent/signals/global/pause` 暂停所有 Agent
2. 随时 `touch .agent/signals/per-scene/01_test/pause` 只暂停 scene 01_test
3. 随时直接编辑 `scenes/` 下的文件
4. 随时用浏览器打开 `.agent/reports/*.html` 查看画面
5. 随时 `rm .agent/signals/per-scene/01_test/review_needed` 让特定 scene 继续

---

## 12. 并发与宿主模型（不含 Multi-Agent 协调）

PRD 不包含跨进程 Multi-Agent：**不在 Harness 层做 scene claim、排队或 exit 4/5**。同一项目内若要并行渲染，请自行用外层编排（或通过 `render-all`/composite 的线程池在本机并行**不同目录**）。

仍保留的工程事实：

| 机制 | 用途 |
|------|------|
| **Check Report 锁** | POSIX `flock`，避免并行写同一检查报告 JSON |
| **Git 锁** | `agent-run.sh` / `.agent/.git_lock` 串行化 commit |
| **端口抢占** | 渲染前通过 `bind()` 分配空闲端口（非跨 Agent 协议）|

`project.yaml` 的 `max_concurrent_scenes` 仍可用于 **本机** `render-all` / composite 的并行上限，与已过期的「全局 claim 排队」语义无关。

### 12.1 Stale 状态清理

渲染进程崩溃后，`state.json` 可能长时间停留在 `running`。清理：

```bash
python3 bin/cleanup-stale.py --dry-run
python3 bin/cleanup-stale.py
```

可选 `--logs`：按保留策略裁剪 `.agent/log/*.log`。

---

*文档版本：v0.4*  
*设计原则：UNIX Philosophy + Host Agent "Bash is All You Need"*  
*状态：Phase 0-9 完成；单宿主渲染与检查管线就绪，SOURCEMAP 自动更新 + Git hooks 版本化*
