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
- 需要缓存？使用 `just` 的文件时间戳判断，不内建数据库。
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
├── engines/                 # 渲染引擎适配层（只读模板）
│   ├── manim/
│   │   ├── src/             # 引擎适配源码（Agent 可 grep 学习）
│   │   │   ├── templates/     # 基类模板（CameraScene, setup, construct）
│   │   │   ├── mobjects/      # 自定义 Mobject
│   │   │   └── utils/         # ffmpeg_pipe.py, latex_helper.py
│   │   ├── scripts/
│   │   │   ├── render.sh      # 入口：scene.py + output_dir → 帧序列
│   │   │   ├── inspect.sh     # 打印可用 Mobject / Animation 列表
│   │   │   └── site_packages.sh # 打印 manim 安装路径
│   │   └── Justfile
│   └── motion_canvas/
│       ├── src/
│       │   ├── templates/
│       │   │   └── scene_base.tsx
│       │   └── utils/
│       │       └── mathjax_bridge.ts
│       ├── scripts/
│       │   ├── render.sh
│       │   └── inspect.sh
│       └── Justfile
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
├── pipeline/                # 后处理管道（纯 bash，ffmpeg 驱动）
│   ├── render.sh            # 读取 manifest，分发到引擎渲染脚本
│   ├── concat.sh            # 场景拼接（ffmpeg concat demuxer）
│   ├── add_audio.sh         # 音轨合成（ffmpeg amix / amerge）
│   ├── fade.sh              # 淡入淡出（ffmpeg afade / fade filter）
│   ├── compress.sh          # 输出压缩（CRF / preset 控制）
│   └── preview.sh           # 快速预览（降分辨率 / 抽帧）
│
├── bin/                     # 全局工具脚本
│   ├── macode               # 主入口 CLI
│   ├── agent-shell          # Agent 默认 shell 入口，预装 PATH
│   ├── agent-run.sh         # Git 原子操作包装器
│   ├── safety-gate.sh       # 命令白名单拦截器
│   └── discover             # 交互式项目结构探索助手
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

---

## 4. Host Agent 使用指南（直接调用 CLI）

MaCode 的每个工具都是**独立的 CLI**，可被 Host Agent 的标准 Bash 工具直接调用。无需进入任何自定义 shell。

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

### 4.5 SOURCEMAP 协议 —— Agent 的安全地图

SOURCEMAP 是每个引擎目录下的结构化黑白名单文档（`engines/{name}/SOURCEMAP.md`）。它不是给 Agent 看的文档，而是 **Harness 用来约束和引导 Agent 的协议**。

**核心原则**：
- **使用者 Agent 只读** SOURCEMAP，通过 `macode inspect` 查询 API
- **开发者 Agent 读写** SOURCEMAP，负责维护引擎适配层
- Harness 在启动时将它注入 Agent 的**工作记忆**，在编码时用它做**审查门**，在出错时用它做**诊断地图**

**Agent 工作流中的 SOURCEMAP**：

```bash
# 1. 启动时自动加载（agent-shell 内置）
bin/agent-shell
# → 校验 engines/{engine}/SOURCEMAP.md 存在且版本匹配
# → 提取 P0/P1 API 到 .agent/context/engine_api.txt
# → 提取 BLACKLIST 到 .agent/context/engine_blacklist.txt

# 2. 编码前查询 API
macode inspect --grep "NumberLine\|Axes\|MathTex"
# → 查询 SOURCEMAP WHITELIST，确认 API 存在且安全

# 3. 渲染前自动审查（pipeline/render.sh 内置）
pipeline/render.sh scenes/02_demo/
# → api-gate.py 检查 scene.py 是否包含 BLACKLIST 导入
# → 若发现 "import manimlib" → 立即阻断，提示修复

# 4. 出错时定向诊断（engines/*/scripts/render.sh 内置）
# → 日志解析器扫描错误关键词
# → 匹配 BLACKLIST 条目 → "你踩了 DEPRECATED_GL，修复方案是 X"
```

**Agent 必须遵守的 SOURCEMAP 规则**：
1. 禁止直接编辑 `engines/{name}/SOURCEMAP.md`
2. 在场景代码中 `import` 未确认的模块前，先用 `macode inspect --grep` 查 WHITELIST
3. 被 `api-gate.py` 拦截时，必须先修复违规导入再渲染
4. 渲染失败时，先读日志中的 SOURCEMAP 诊断建议，不盲目重试
5. 禁止 `grep -r` 整个引擎源码树 —— 用 `macode inspect` 按图索骥

**SOURCEMAP 维护触发条件**（开发者关注）：
- 引擎版本升级（`pip install --upgrade manim` / `npm update`）
- Agent 误入陷阱（复盘后补入 BLACKLIST）
- 适配层新增代码（`engines/{name}/src/` 下新增文件）
- 扩展计划变更（EXTENSION 中的 TODO → DONE/WONTFIX）

**验证**：生成或修改 SOURCEMAP.md 后必须运行：
```bash
engines/{name}/scripts/validate_sourcemap.sh
```

---

## 5. 安全模型：分层防御（Host Agent 自主 + MaCode 辅助）

MaCode 不强制控制 Host Agent，而是提供**可选的安全工具**，由 Host Agent 决定是否调用。

### 5.1 渲染前静态检查（api-gate.py）

```bash
# 独立校验工具，Host Agent 可在渲染前调用
bin/api-gate.py scenes/02_fourier/scene.py engines/manim/SOURCEMAP.md
# → 检查 BLACKLIST 导入 + sandbox 危险调用
# → 退出码 0 = 通过，1 = 拦截（输出具体违规位置）
```

`pipeline/render.sh` 已内置自动调用，但 Host Agent 也可在编码阶段手动预检。

### 5.2 Git 原子操作（agent-run.sh，可选）

```bash
# 可选包装器，Host Agent 可决定是否使用
bin/agent-run.sh "pipeline/render.sh scenes/02_fourier/"
# → git stash + checkout -b agent/task → 执行命令 → commit/merge 或 rollback
```

**注意**：Host Agent 也可直接使用自己的 Git 工具，不强制使用 `agent-run.sh`。

### 5.3 资源熔断（render.sh 内置）

```bash
# pipeline/render.sh 内置熔断，无需 Host Agent 干预
# - 帧数上限：10000
# - 磁盘上限：50GB
# - 渲染超时：600s（读取 project.yaml）
```

### 5.4 本地开发保护（safety-gate.sh，人类用户可选）

```bash
# 仅用于人类用户本地开发，不作用于 Host Agent
bin/agent-shell   # 进入带 safety-gate 的交互式 shell
# READLINE Enter-key 拦截危险命令
```

**Host Agent 无需使用 safety-gate**——它有自己的安全策略。


---

## 6. 引擎选型策略

### 6.1 默认引擎：ManimCE
- **理由**：生态最成熟，Agent 训练数据丰富，LaTeX 支持原生，3Blue1Brown 风格标杆。
- **约束**：必须通过 `engines/manim/scripts/render.sh` 调用，Agent 不直接执行 `python -m manim`。

### 6.2 轻量备选：Motion Canvas
- **理由**：热重载友好，实时预览加速 Agent 迭代，MIT 协议无商业限制。
- **约束**：通过 `engines/motion_canvas/scripts/render.sh` 统一入口。

### 6.3 3D 备选：DefinedMotion / Three.js 原生
- **理由**：基于 Three.js，Agent 理解成本低，3D 几何可视化强。
- **约束**：待 Phase 2（引擎抽象层）引入，Phase 0/1 不实现。

### 6.4 明确不选
- **Remotion（作为主引擎）**：通用视频 / 营销视频工具，数学动画需要从零写 SVG/Canvas 绘制逻辑，无内置数学对象抽象。它更适合作为"最终拼接层"（若需将动画片段与 UI 数据结合），而非数学动画主引擎。
- **SoX（音频处理）**：Windows 下管道不可靠，MP3 支持经常缺失，PowerShell 集成体验差。所有音频处理统一由 `ffmpeg` 完成，保持依赖单一化。

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
| `bin/macode inspect --grep <re>` | 查询 API | `bin/macode inspect --grep "Circle\|MathTex"` | 匹配的 WHITELIST 条目 |
| `bin/api-gate.py <scene.py> <SOURCEMAP>` | 代码审查 | `bin/api-gate.py scenes/01_test/scene.py engines/manim/SOURCEMAP.md` | 退出码 0/1 + 违规列表 |
| `bin/detect-hardware.sh` | 硬件检测 | `bash bin/detect-hardware.sh` | `.agent/hardware_profile.json` |
| `bin/select-backend.sh` | 后端选择 | `bash bin/select-backend.sh` | `gpu` / `d3d12` / `cpu` / `headless` |
| `pipeline/concat.sh <frames_dir> <out.mp4> [fps]` | 帧序列编码 | `pipeline/concat.sh .agent/tmp/01_test/frames/ out.mp4 30` | MP4 文件 |
| `pipeline/add_audio.sh <video> <audio> <out>` | 音轨合成 | `pipeline/add_audio.sh out.mp4 bgm.mp3 final.mp4` | MP4 文件 |
| `pipeline/compress.sh <in> <out>` | 视频压缩 | `pipeline/compress.sh final.mp4 small.mp4` | MP4 文件 |
| `pipeline/preview.sh <mp4>` | 快速预览 | `pipeline/preview.sh final.mp4` | 降分辨率预览文件 |
| `engines/*/scripts/inspect.sh` | 引擎能力查询 | `engines/manim/scripts/inspect.sh` | 可用模板/API 列表 |

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
4. 编写场景源码（`scene.py` + `manifest.json`）
5. 可选：预检 `bin/api-gate.py` 确认无违规导入
6. 调用 `pipeline/render.sh <scene_dir>` 渲染
7. 若失败：`tail .agent/log/*.log` 查看诊断
8. 后处理：`pipeline/*.sh` 拼接 / 音频 / 压缩

---

*文档版本：v0.2*  
*设计原则：UNIX Philosophy + Claude Code "Bash is All You Need"*  
*状态：Phase 0-3 完成，Phase 4 进行中*
