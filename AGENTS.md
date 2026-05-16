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
- 绝不内建「一站式」黑盒：没有 `render_and_upload()` 这类封闭 API；渲染与交付由 `pipeline/render.sh`、`python3 pipeline/deliver.py …` 等可组合脚本完成（仓库内无 `upload.sh`）。

### 2.2 文本流是通用接口
- 场景契约：`scenes/*/manifest.json`（JSON 文本）。
- 帧清单：部分管道会生成 `.agent/tmp/{scene}/frames/list.txt`（每行一个文件路径；依编排器/缓存路径而定）。
- 时间码：音频对齐等场景可使用 `timeline.csv`（常由 `pipeline/audio-analyze.sh` 生成，多在 `assets/` 或场景目录下；非每个场景都有）。
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
- 引擎源码必须可被 `grep`：Agent 通过 `find $(python -c "import manim; print(manim.__path__[0])") -name "*.py" | xargs grep "class Circle"` 学习 API，而非查阅封闭文档。
- 所有命令执行日志写入 `.agent/log/`，Agent 出错时先查看最近日志，例如：`tail -n 50 "$(ls -t .agent/log/*.log 2>/dev/null | head -1)"`。
- 音频处理不隐藏为内部库调用，Agent 直接阅读 `pipeline/add_audio.sh` 中的 `ffmpeg` 命令。

### 2.5 优先使用工具而非机制
- 需要音频合成？调用 `ffmpeg -f lavfi` 生成测试音，不内建音频引擎。
- 需要公式渲染？调用 `pdflatex` 或 `mathjax-node-cli`，不内建排版系统。
- 需要缓存？使用文件时间戳和内容哈希判断（`bin/sourcemap-sync.py` 的 `content_hash`），不内建数据库。
- 需要视频剪辑？调用 `ffmpeg` 的 filtergraph，不内建时间轴编辑器。

---

## 3. 系统架构

MaCode 采用**三层解耦架构**（Scene 描述 → Engine 适配 → 基础设施），使场景在引擎间可移植。

完整目录结构、三层解耦细节见 → [`docs/architecture.md#1-系统架构总览`](docs/architecture.md#1-系统架构总览)。

---

## 4. Host Agent 快速入门

MaCode 的每个工具都是**独立的 CLI**，可被 Host Agent 的标准 Bash 工具直接调用。无需进入任何自定义 shell。

执行具体任务时，建议先读取 `.agents/skills/macode-host-agent/SKILL.md` 获取结构化工作流；本章节提供最小必要上下文。

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

### 4.2 编写与渲染（标准工作流）

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

**`.py` 场景 manifest 示例**：
```json
{
  "engine": "manim",
  "duration": 5,
  "fps": 30,
  "resolution": [1920, 1080]
}
```

**`.tsx` 场景（Motion Canvas）** 通过 `manifest.json` 中的 `"engine": "motion_canvas"` 自动路由：
```bash
macode render scenes/02_shader_mc/
# 或分步调试：macode mc serve scenes/02_shader_mc/
```

MC 场景的完整 manifest 示例和渲染细节见 → [附录 A.1](#a1-motion-canvas-渲染细节)。

### 4.3 批量渲染与后处理

```bash
# 批量渲染所有场景
bin/render-all.sh

# 多段 MP4 拼接（videos 模式：第 1 个参数为输出文件，其后为输入文件）
pipeline/concat.sh output/lecture.mp4 .agent/tmp/00_title/final.mp4 .agent/tmp/01_intro/final.mp4

# 音频合成
pipeline/add_audio.sh output/lecture.mp4 assets/bgm.mp3 output/final.mp4

# 压缩（社交媒体版本）
pipeline/compress.sh output/final.mp4 output/final_small.mp4
```

### 4.4 Composite 场景（模块化合成）

将复杂场景拆分为独立 Segment，分别渲染后硬切拼接。Segment 间通过 `params` 共享主题参数。

```bash
# 从模板创建
macode composite init scenes/09_lecture --template intro-main-outro

# 渲染（与单场景入口相同）
pipeline/render.sh scenes/09_lecture/
```

Composite manifest 示例和参数注入细节见 → [附录 A.4](#a4-composite-场景参考)。

---

## 5. 安全模型

MaCode 的安全策略是**诚实且轻量的**：在渲染管道中拦截最常见的错误（跨引擎导入），在 Git 层面保护基础设施目录不被误改。我们不提供运行时沙箱——如果你需要隔离不可信代码，请在容器或独立用户中运行 Harness。

### 5.1 渲染时导入检查（api-gate）

`bin/api-gate.py` 在渲染前自动执行，对照 `engines/<engine>/sourcemap.json` 的 BLACKLIST 拦截违规导入：

```bash
# 手动调用示例
python3 bin/api-gate.py scenes/01_test/scene.py engines/manim/sourcemap.json --engine manim
```

真正产生价值的是 BLACKLIST 和 REDIRECT：
- **BLACKLIST**：阻止跨引擎导入（如 ManimCE 场景写 `from manimlib import *`）
- **REDIRECT**：提示 Agent "不要手写 X，用 Y 替代"（如手写 ffmpeg 字符串 → 使用 `utils.ffmpeg_builder`）

### 5.2 Git 拦截（pre-commit / pre-push）

Hooks 模板在 `.githooks/`，由 `bin/install-hooks.sh` 安装：

- **`pre-commit`**：阻止对 `engines/`、`bin/`、`pipeline/` 及根目录 `project.yaml`、`requirements.txt`、`package.json` 的暂存修改。
- **`pre-push`**：对所有可渲染场景运行 `api-gate.py` 导入检查。

Bypass：`git commit --no-verify` / `git push --no-verify`（人类维护基础设施时使用）。

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

### 6.6 WSL2 调优

> WSL2 用户必读：项目位置、`.wslconfig`、GPU 驱动检测的详细约束见 → [`docs/architecture.md#3-wsl2-运行环境调优`](docs/architecture.md#3-wsl2-运行环境调优)。
> 自动检测：`bash bin/check-wsl2.sh`

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
└── render.log         # 引擎输出目录下的 tee 日志（依引擎与调用路径而定，非全局 log）
```

### 7.3 日志规范
所有脚本必须将 stderr + stdout 追加到 `.agent/log/YYYYMMDD_HHMMSS_{script_name}.log`，Agent 调试时通过 `tail` 读取。

---

## 8. 反模式（Agent 禁止做的事）

1. **不要内建 IDE**：Agent 不需要"智能提示"，它需要 `grep` 和 `find`。
2. **不要抽象过度**：不要为 Manim 和 Motion Canvas 创建统一的 Python/TypeScript SDK。契约在 `manifest.json`，编排与落盘在 `pipeline/`（含 `.sh` 与 `.py`）中完成。
3. **不要隐藏中间状态**：禁止将帧序列输出为内存流或临时删除。Agent 必须能 `ls` 看到每一帧。
4. **不要动态下载依赖**：Agent 禁止执行 `pip install` 或 `npm install`。依赖必须在项目初始化时固化（`requirements.txt`、`package-lock.json`、Docker 镜像）。
5. **不要假设引擎版本**：Agent 必须通过 `engines/*/scripts/inspect.sh` 查询能力，不硬编码 API。
6. **不要引入额外音频工具**：所有音频处理由 `ffmpeg` 完成，禁止调用 `sox`、`audacity` 或其他音频处理软件。
7. **不要绕过 SOURCEMAP 审查**：禁止直接修改 `engines/{name}/SOURCEMAP.md`。禁止在 `api-gate.py` 拦截后强行渲染。禁止 `grep -r` 整个引擎源码树 —— 用 `macode inspect` 按图索骥。
8. **不要忽略 SOURCEMAP 诊断**：渲染失败时先读日志中的定向诊断建议，不盲目重试。错误信息指向 BLACKLIST 条目时，按提示修复而非绕过。

---

## 9. CLI 工具速查表（Host Agent 参考）

| 工具 | 典型任务 | 调用示例 | 输出 |
|------|----------|----------|------|
| `pipeline/render.sh <scene_dir>` | 渲染单个场景 | `pipeline/render.sh scenes/01_test/` | `.agent/tmp/{scene}/final.mp4` |
| `bin/render-all.sh` | 批量渲染项目所有场景 | `bin/render-all.sh --parallel 4` | 各场景 `final.mp4` |
| `bin/macode status` | 查看项目健康状态 | `bin/macode status` | 文本摘要 |
| `bin/macode check <scene_dir>` | 静态检查场景合规性 | `macode check scenes/01_test --static` | 检查报告 JSON |
| `bin/macode cleanup [--dry-run]` | 清理 stalled 进程和日志 | `macode cleanup --dry-run` | 清理报告 |
| `bin/install-hooks.sh [--check]` | 安装/检查 git hooks | `bin/install-hooks.sh --check` | 安装报告 |
| `bin/macode dry-run <scene_file>` | 预渲染验证（语法、导入、LaTeX） | `macode dry-run scenes/01_test/scene.py` | 通过/失败 + 问题列表 |
| `bin/macode inspect --grep <re>` | 查询引擎 API 是否在白名单 | `macode inspect --grep "Circle\|MathTex"` | 匹配的 WHITELIST 条目 |
| `macode sourcemap health` | SOURCEMAP 快速健康检查 | `macode sourcemap health` | 版本漂移 + 一致性摘要 |
| `macode sourcemap validate <engine>` | SOURCEMAP 深度校验 | `macode sourcemap validate manim` | 校验 + 路径检查 |
| `bin/api-gate.py <scene.py> <sourcemap.json> [--engine]` | 手动运行导入审查 | `bin/api-gate.py scenes/01_test/scene.py engines/manim/sourcemap.json --engine manim` | 退出码 0/1/2 |
| `bin/calc-preview-duration.py <manifest>` | 计算预览时长 | `calc-preview-duration.py scenes/01_test/manifest.json` | 秒数（如 `3.0`） |
| `bin/patch-manifest.py <manifest>` | 原子修改 manifest | `patch-manifest.py m.json --duration 3 --fps 10` | 原子写回，支持 `--backup` |
| `bin/watch-file.sh <file>` | 轮询监听文件变化 | `watch-file.sh scene.py --exec "echo changed"` | 变化时执行命令 |
| `cat .agents/skills/{engine}/SKILL.md` | 查阅引擎 API 参考 | `cat .agents/skills/manimce-best-practices/SKILL.md` | 完整引擎 API 文档 |
| `pipeline/concat.sh <out.mp4> <in1> [in2...]` | 多段视频硬切拼接 | `pipeline/concat.sh output/lecture.mp4 seg1.mp4 seg2.mp4` | MP4 文件 |
| `pipeline/add_audio.sh <video> <audio> <out>` | 音轨合成 | `pipeline/add_audio.sh out.mp4 bgm.mp3 final.mp4` | MP4 文件 |
| `pipeline/compress.sh <in> <out>` | 视频压缩（社交媒体） | `pipeline/compress.sh final.mp4 small.mp4` | MP4 文件 |
| `pipeline/preview.sh <mp4>` | 快速预览（降分辨率） | `pipeline/preview.sh final.mp4` | 降分辨率预览文件 |
| `bin/macode-dev.sh <scene_dir> [opts]` | 启动引擎 dev 模式 | `macode-dev.sh scenes/01_test` | 实时预览/快照 |
| `engines/*/scripts/inspect.sh` | 查询引擎能力 | `engines/manim/scripts/inspect.sh` | 可用模板/API 列表 |
| `macode mc serve <scene_dir>` | 启动 MC dev server | `macode mc serve scenes/02_shader_mc/` | 端口输出到 stdout |
| `macode mc stop <scene_dir>` | 停止 MC dev server | `macode mc stop scenes/02_shader_mc/` | SIGTERM → SIGKILL |
| `macode shader list` | 列出 Layer 2 shader 素材 | `macode shader list` | 注册表中的所有素材 |
| `macode shader render <dir>` | 预渲染 shader 到 PNG | `macode shader render assets/shaders/lygia_fire/` | 输出到 `shader_dir/frames/` |

### 退出码约定

| 退出码 | 含义 |
|--------|------|
| 0 | 成功 |
| 1 | 通用错误 / api-gate 拦截 |
| 124 | 渲染超时（timeout 触发）|

### Host Agent 工作流建议

1. 读取 `project.yaml` 了解配置
2. 读取目标 `scenes/*/manifest.json` 理解需求
3. 按 `manifest.json` 的 `engine` 字段查阅 `.agents/skills/{engine}/SKILL.md`
4. 使用 `macode inspect --grep <keyword>` 或 `engines/*/scripts/inspect.sh` 查询 API
5. 编写场景源码（`scene.py` + `manifest.json`）
6. 可选：预检 `bin/api-gate.py` 确认无违规导入
7. 调用 `pipeline/render.sh <scene_dir>` 渲染
8. 若失败：`tail .agent/log/*.log` 查看诊断
9. 后处理：`pipeline/concat.sh` / `add_audio.sh` / `compress.sh` 等；交付可选 `python3 pipeline/deliver.py <scene> <tmp_dir> output/`

---

## 10. 深度参考（附录）

本附录包含进阶组件和系统的完整参考。日常渲染任务无需阅读。

### A.1 Motion Canvas 渲染细节

Motion Canvas 场景通过 `manifest.json` 中的 `"engine": "motion_canvas"` 自动路由到 Harness 2.0：

```bash
# 完整渲染（自动启动 dev server → 抓帧 → 清理）
macode render scenes/02_shader_mc/
# 或显式传参
macode render scenes/02_shader_mc/ --fps 30 --duration 3 --width 1920 --height 1080

# 分步控制（开发调试）
macode mc serve scenes/02_shader_mc/        # 启动 dev server，输出随机端口
macode mc stop scenes/02_shader_mc/         # 停止 dev server

# 单帧截图（`render.mjs --snapshot`）
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

**Harness 2.0 CLI**：`engines/motion_canvas/scripts/render.mjs` 合并了原 `serve.mjs` / `stop.mjs` / `playwright-render.mjs`：批量渲染时在同一进程内拉起 Vite、Playwright 抓帧、再杀掉 dev server；`macode mc serve|stop` 映射为 `render.mjs --serve-only` 与 `render.mjs --stop`。不再使用独立的 Browser Pool 与 `server-guardian.mjs`。

### A.2 Zone/Region 布局系统（ManimGL + ManimCE）

> **引擎支持声明**：ZoneScene 布局系统已在 **ManimGL** 和 **ManimCE** 中实现。Motion Canvas 无等价实现 —— 其声明式 React 节点模型与命令式 zone placement 没有自然映射。

声明式空间约束系统，确保数学对象按语义区域放置。

**核心组件**：
- **`ZoneScene`**：基类，提供 `place(mobj, zone_name)`、`place_in_grid(...)`、`zone_center(...)` 等 API。子类通过 `LAYOUT_PROFILE` 选择布局模板。
- **`layout_geometry.py`**：纯几何计算（像素 ↔ Manim 单位转换、zone 边界、对齐点计算），无引擎依赖。
- **`layout_validator.py`**：约束验证（max_objects、allowed_types、primary_zone 非空检查）。

**典型布局模板**：
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

`self.place(mobj, zone_name)` 自动处理像素 ↔ Manim 单位转换、zone 边界和对齐点计算，无需手写坐标。渲染前，`bin/check-layout.py` 自动验证 zone 约束（overflow、overlap、whitespace、font size）。

### A.3 Narrative 叙事模式（ManimGL + ManimCE）

> **引擎支持声明**：NarrativeScene 已在 **ManimGL** 和 **ManimCE** 中实现。动画原语自动映射到各引擎的正确名称（ManimGL 的 `ShowCreation` → ManimCE 的 `Create`）。Motion Canvas 无等价实现。

叙事模板驱动的场景编排，将数学讲解抽象为可复用的叙事阶段（stage）。

**核心组件**：
- **`NarrativeScene`**：继承 `ZoneScene`，提供 `stage(stage_id, *mobjects)` 方法。自动验证阶段顺序、选择动画原语、检查主视觉区首次出现时间。
- **Narrative Templates**：
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

### A.4 Composite 场景参考

Composite 将复杂场景拆分为独立 Segment，分别渲染后硬切拼接。Segment 间通过 `params` 共享主题参数。

**创建 composite 场景**：
```bash
# 从模板创建（支持 --engine manim / motion_canvas）
macode composite init scenes/09_lecture --template intro-main-outro
# → 生成 shots/00_intro, shots/01_main, shots/02_outro + 顶层 manifest.json

# 添加 segment（自动检测引擎类型）
macode composite add-segment scenes/09_lecture bonus --after main
```

**Composite manifest 契约**（当前仅支持硬切拼接，不支持转场/音频/叠加）：
```json
{
  "type": "composite-unified",
  "segments": [
    {"id": "intro", "scene_dir": "shots/00_intro"},
    {"id": "main", "scene_dir": "shots/01_main"},
    {"id": "outro", "scene_dir": "shots/02_outro"}
  ],
  "params": {"theme_color": "#1E90FF", "title_text": "讲座标题"}
}
```

**参数注入**：Segment 源码通过环境变量读取 composite 参数：
- **Manim**: `json.load(open(os.environ["MACODE_PARAMS_JSON"]))`
- **Motion Canvas**: `(window as any).__MACODE_PARAMS`（由 `render.mjs` 自动注入）

**渲染**：
```bash
pipeline/render.sh scenes/09_lecture/
# 或（内部同样调用 pipeline/render.sh）
macode composite render scenes/09_lecture
```

> **入口**：复合场景**没有**单独的「只渲染 composite」子命令之外的魔法入口；`macode composite render` 与直接执行 `pipeline/render.sh` 等价，均由 `render.sh` 按 `type` 分发到 `composite-unified-render.py`。

### A.5 SOURCEMAP 协议

SOURCEMAP 是 Harness 用来约束和引导 Agent 的 API 安全协议。

- **使用者 Agent 只读**：通过 `macode inspect` 查询 API
- **开发者 Agent 读写**：负责维护引擎适配层的 `engines/{name}/sourcemap.json`

完整协议文档（维护工具链、验证流程、触发条件）见 → [`docs/sourcemap-protocol.md`](docs/sourcemap-protocol.md)。

---

## 11. 人类介入 / 并发模型

- **人类介入协议**：`.agent/signals/{global,per-scene}/*` — 见 → [`docs/architecture.md#4-人类介入协议`](docs/architecture.md#4-人类介入协议)
- **并发模型**：`project.yaml` → `agent.resource_limits.max_concurrent_scenes`（本机并行；PRD 已删除 Multi-Agent 协调）— 见 → [`docs/architecture.md#5-并发与宿主模型`](docs/architecture.md#5-并发与宿主模型)

---

*文档版本：v0.6*  
*设计原则：UNIX Philosophy + Host Agent "Bash is All You Need"*  
*状态：Phase 0-9 完成；单宿主渲染与检查管线就绪；composite 默认 unified 路由；SOURCEMAP 真源为 `sourcemap.json`；Git hooks 版本化*
