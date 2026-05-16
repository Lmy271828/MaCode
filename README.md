# MaCode — UNIX 原生的数学动画制作 Harness

> **Ma**th + **Code**. Make it work, then make it right, then make it fast.

MaCode 是一个 Bash-First 的数学动画 Agent 工作流系统。它不封装高级 API，而是提供一个**透明的、可被 `ls` / `cat` / `grep` 完全理解的文件系统环境**，让 Agent 通过 Bash 命令探索、组合、修复数学动画的每一个环节。

## 设计哲学

- **引擎无关**：场景定义与引擎实现解耦。ManimCE → Motion Canvas 迁移只需修改 `manifest.json`。
- **管道透明**：渲染、剪辑、压缩的每一步都是可见的文件转换。
- **状态可逆**：所有 Agent 行为通过 Git 流控制实现原子化与可回滚。
- **音频统一**：所有音频处理由 `ffmpeg` 完成，不引入额外依赖。

## 快速开始

MaCode 是**Host-Agent-First**的 Harness。首选使用方式是让 Host Agent（Claude Code、Cursor、Kimi 等）在项目中直接调用 CLI；人类用户可在无 Agent 会话时手动操作。

### 方式一：Host Agent 启用（推荐）

在 MaCode 项目目录启动你的 Host Agent 会话。Agent 会自动读取 `AGENTS.md` 和 `project.yaml` 理解项目架构。

```bash
# 1. 初始化项目（由 Host Agent 执行）
bash bin/setup.sh

# 2. Agent 读取 Skill 获取工作流模板
cat .agents/skills/macode-host-agent/SKILL.md

# 3. Agent 直接调用 CLI 完成场景编写与渲染
pipeline/render.sh scenes/01_test/
macode status
macode inspect --grep "Circle"
```

> **💡 提示**：若你的 AI 工具不支持自动读取项目级 skill，可复制以下系统提示给它：
> ```bash
> bin/agent --prompt
> ```

Host Agent 的标准工作流：
1. 读取目标 `scenes/*/manifest.json` 理解需求
2. 用 `macode inspect --grep <keyword>` 查询引擎 API
3. 编写场景源码（`scene.py` / `scene.tsx` + `manifest.json`）
4. `pipeline/render.sh <scene_dir>` 渲染
5. 若失败：`tail -n 50 .agent/log/*.log` 查看诊断

---

### 方式二：人类手动操作（无 Host Agent 会话）

```bash
# 克隆项目
git clone <repo-url> MaCode && cd MaCode

# 初始化（用户版）
bash bin/setup.sh

# 设置 PATH
export PATH="$PWD/bin:$PATH"

# 检查环境
bin/agent --check

# 查看状态
macode status

# 渲染单个场景
pipeline/render.sh scenes/01_test/

# 批量渲染
bin/render-all.sh

# 并行渲染（最多 4 个场景同时）
bin/render-all.sh --parallel 4

> 开发/测试环境请使用 `bin/setup-dev.sh`（额外安装 pytest、ruff 并自动运行 smoke 测试）。

### 可选：渲染时人工标记坏帧（Copilot feedback）

渲染管道**不会**自动启动本工具。若在本地交互调试时希望在出帧过程中用 **Ctrl+F** 记录当前帧序号与备注，可在**另一终端**、仓库根目录执行：

```bash
python3 bin/copilot-feedback.py watch <场景目录名>
# 当渲染子进程有已知 PID、希望在进程结束后自动退出 watch 时：
python3 bin/copilot-feedback.py watch <场景目录名> --pid <ENGINE_PID>
```

记录会追加到 `.agent/signals/frame_feedback.jsonl`。字段约定见 `docs/task-state-schema.md` 与源码注释。

## 目录结构

```text
macode/
├── .macode/                # Agent 运行时状态（保留目录，不再存放 API Key）
├── .agent/                 # Agent 工作区（临时帧、缓存、日志）
│   ├── tmp/{scene}/        # 帧序列、渲染输出
│   ├── cache/              # 帧级缓存（按内容哈希寻址）
│   ├── context/            # 注入 Agent 的引擎副本（如 sourcemap 摘要）
│   └── log/                # 全局渲染日志
├── engines/                # 渲染引擎适配层
│   ├── manim/              #   ManimCE（Python，batch / CI 常用）
│   │   ├── SOURCEMAP.md    #     源码地图（Agent 的 API 导航）
│   │   ├── scripts/        #     render.sh, inspect.sh, validate_sourcemap.sh
│   │   └── src/            #     适配层模板与工具（scene_base, latex_helper, ffmpeg_builder...）
│   ├── manimgl/            #   ManimGL（Python，interactive 预览引擎）
│   │   ├── SOURCEMAP.md
│   │   ├── scripts/
│   │   └── src/
│   └── motion_canvas/      #   Motion Canvas（TypeScript）
│       ├── SOURCEMAP.md
│       ├── scripts/
│       └── src/templates/
├── scenes/                 # 用户场景（Agent 主要工作区）
│   ├── 00_title/           #   序号前缀保证管道拼接顺序
│   │   ├── manifest.json   #     场景契约（引擎类型、时长、依赖）
│   │   └── scene.py        #     引擎实现
│   └── ...
├── pipeline/               # 渲染管道（编排层 + 执行层）
│   ├── render.sh           #   顶层路由（按 manifest.type 分发）
│   ├── render-scene.py     #   单场景编排（validate → api-gate → cache → engine → deliver）
│   ├── composite-unified-render.py  #   composite-unified 编排入口
│   ├── validate-manifest.py #   manifest 校验
│   ├── _render/            #   内部子包（orchestrator、encode、validate 等）
│   ├── concat.sh           #   帧序列 → MP4
│   ├── add_audio.sh        #   音轨合成
│   ├── audio-analyze.sh    #   音频响度/静音分析（智能剪辑等）
│   ├── fade.sh             #   淡入淡出
│   ├── compress.sh         #   输出压缩
│   ├── preview.sh          #   快速预览
│   ├── smart-cut.sh        #   静默段自动剪辑
│   ├── thumbnail.sh        #   关键帧提取
│   ├── cache.sh            #   帧级缓存
│   └── deliver.py          #   产物交付 + 输出侧 _manifest.json（.agent/tmp/ → output/）
├── bin/                    # 全局工具脚本
│   ├── setup.sh             #   项目初始化 — 用户版（不暴露测试依赖）
│   ├── setup-dev.sh         #   项目初始化 — 开发版（含测试框架 + 验证）
│   ├── agent                #   配置检查 + 系统提示生成
│   ├── human-tools/         #   人类可选：safety-gate.sh、agent-shell
│   ├── macode               #   主入口 CLI（render / status / inspect）
│   ├── macode-run           #   统一进程生命周期管理器（Harness 2.0）
│   ├── api-gate.py          #   BLACKLIST 导入扫描
│   ├── composite-init.py    #   macode composite init / add-segment
│   ├── composite-assemble.py #   Composite 组装执行层（overlay → transition → audio）
│   ├── composite-transition.py
│   ├── composite-overlay.py
│   ├── composite-audio.py
│   ├── composite-cache.py
│   ├── render-all.sh        #   批量渲染（支持 --parallel）
│   └── discover             #   交互式项目结构探索
├── project.yaml            # 全局配置（引擎、分辨率、安全策略）
└── docs/
    ├── SOURCEMAP_SPEC.md   # SOURCEMAP 规范
    ├── progress.md         # 开发路线图
    └── C-shader-pipeline-plan.md  # Shader 管道架构
```

## 核心概念

### 三层解耦

```
Layer 3: Scene 描述 (manifest.json)  ← 唯一不变层，引擎无关
Layer 2: Engine 适配 (engines/*)     ← 可替换层
Layer 1: 基础设施 (bash, ffmpeg, git) ← 绝对稳定层
```

### SOURCEMAP 协议

机器真源为 `engines/<engine>/sourcemap.json`；同目录下的 `SOURCEMAP.md` 由 `bin/sourcemap-sync.py` 生成，是 Agent 的**人类可读源码探索地图**：

- **WHITELIST**：安全的、值得阅读的 API 表面（P0/P1/P2 分级）
- **BLACKLIST**：陷阱路径（废弃 API、内部黑魔法、测试代码）
- **EXTENSION**：引擎支持但 MaCode 尚未接入的能力

Agent 通过 `macode inspect --grep <keyword>` 查询，渲染前 `api-gate.py` 自动拦截 BLACKLIST 导入。

### 场景契约 (manifest.json)

```json
{
  "engine": "manimgl",
  "duration": 10,
  "fps": 30,
  "resolution": [1920, 1080],
  "assets": ["assets/formula.tex"],
  "dependencies": ["scenes/00_title/manifest.json"]
}
```

（单场景可将 `engine` 设为 `manim`（ManimCE，CI/无头）、`manimgl` 或 `motion_canvas`；项目级默认见下节 `project.yaml`。）

## 配置

### 项目配置（`project.yaml`）

```yaml
defaults:
  engine: manimgl
  resolution: [1920, 1080]
  fps: 30
```

> 真源以仓库根目录 `project.yaml` 为准；上表与当前默认引擎一致。

## Composite Scene System（模块化场景合成）

将复杂场景拆分为独立 Segment，分别渲染后合成。支持转场效果、背景音乐、跨 Segment 参数注入。

### 快速开始

```bash
# 从模板创建 composite 场景
macode composite init scenes/09_lecture --template intro-main-outro

# 添加新 segment（自动检测引擎）
macode composite add-segment scenes/09_lecture bonus --after main

# 查看 composite 结构
macode composite info scenes/04_composite_demo

# 渲染 composite 场景（自动并行渲染独立 segments）
macode composite render scenes/04_composite_demo
# 或等价于
pipeline/render.sh scenes/04_composite_demo/
```

`pipeline/render.sh` 识别 `manifest.type` 为 `composite-unified` 的场景并进入统一编排路径。

### Composite manifest 示例

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

参数注入：Manim 系 Segment 通过 `os.environ["MACODE_PARAMS_JSON"]` 读取；Motion Canvas Segment 在渲染时由 Harness 注入 `(window as any).__MACODE_PARAMS`（见 `AGENTS.md`）。

---

## 工作流示例

```bash
# 1. 查看项目配置
bin/agent --check

# 2. 查看 ManimCE 引擎提供了什么
engines/manim/scripts/inspect.sh

# 3. 搜索特定 API
macode inspect --grep "NumberLine\|Axes"

# 4. 编写场景（scene.py + manifest.json）到 scenes/02_fourier/

# 5. 渲染（自动通过 api-gate 审查 + 缓存检查）
pipeline/render.sh scenes/02_fourier/

# 6. 如果渲染失败，查看日志中的 SOURCEMAP 诊断
tail -50 .agent/log/$(ls -t .agent/log/ | head -1)

# 7. 预览
pipeline/preview.sh .agent/tmp/02_fourier/final.mp4

# 8. 交付到 output/ 目录（需场景名、临时目录、输出目录三个参数）
python3 pipeline/deliver.py 02_fourier .agent/tmp/02_fourier output/

# 9. 多场景拼接 + 音频合成
pipeline/concat.sh output/*.mp4 output/lecture.mp4
pipeline/add_audio.sh output/lecture.mp4 assets/bgm.mp3 output/final.mp4
```

## 引擎与环境管理

默认引擎以仓库根目录 `project.yaml` 的 `defaults.engine` 为唯一真源。The canonical default engine is `defaults.engine` in `project.yaml` at the repository root.

| 引擎 | 语言 | 模式 | 适用场景 |
|------|------|------|----------|
| ManimCE | Python | batch | CI / 无头、确定性输出、LaTeX 与几何动画 |
| ManimGL | Python | interactive | 本地 OpenGL 预览、快速迭代 |
| Motion Canvas | TypeScript | batch | 热重载、Shader、Web 原生工作流 |

### 环境隔离原则

- **Python**：由 `uv` 统一管理：项目根目录下 `.venv/`（ManimCE）与 `.venv-manimgl/`（ManimGL）分离；依赖仅安装于上述 venv，不使用全局 `pip` 或 `conda`。
- **Node.js**：Motion Canvas 通过 `npx` 调用，`npm install` 将依赖安装到项目本地 `node_modules/`，不污染全局 npm。
- **硬件自适应**：`bin/detect-hardware.sh` 自动检测 GPU / OpenGL / CUDA，生成 `.agent/hardware_profile.json`；`bin/select-backend.sh` 根据画像选择最优后端。

### 构建脚本

| 脚本 | 适用对象 | 安装内容 | 测试暴露 |
|------|---------|---------|---------|
| `bin/setup.sh` | 用户 / Host Agent | 运行时引擎（ManimCE、ManimGL、Motion Canvas） | ❌ 不安装 pytest/ruff，不运行测试 |
| `bin/setup-dev.sh` | 开发者 / CI | 运行时引擎 + 开发依赖（pytest、ruff） | ✅ 自动运行 smoke + unit 测试 |

用户版 `setup.sh` 故意**不暴露测试基础设施**，防止 Host Agent 在场景编写过程中误修改 `tests/` 目录或引入测试依赖到生产环境。开发/贡献请使用 `setup-dev.sh`。

一步完成全部引擎配置：
```bash
# 用户版（推荐）
bash bin/setup.sh

# 开发版（包含测试验证）
bash bin/setup-dev.sh
```

迁移引擎只需修改 `manifest.json` 的 `engine` 字段并重写场景文件，管道脚本无需改动。

### 开发者注意事项

**Git Hooks**：`setup.sh` / `setup-dev.sh` 会自动安装提交拦截 hooks（源模板在 `.githooks/`，受版本控制）：
```bash
# 手动检查 hooks 是否最新
bin/install-hooks.sh --check

# 手动更新（模板变更后）
bin/install-hooks.sh
```

- `pre-commit`：拦截对 `bin/`、`engines/`、`pipeline/` 以及根目录 `project.yaml`、`requirements.txt`、`package.json` 的误修改。
- `pre-push`：推送前对所有可渲染场景运行 `api-gate.py` 导入检查。

**基础设施维护**：当你需要修改上述受保护路径时，pre-commit 会拒绝提交。这是设计行为 —— 请使用 `git commit --no-verify` 并确保修改经过人工 review。

## 安全模型

渲染链路中的安全检查：

```
Host Agent 调用
  → api-gate.py（BLACKLIST 导入检查，由渲染管线自动触发）
  → pipeline/render.sh → render-scene / composite-unified-render
  → 熔断与上限（帧数 / 磁盘 / 超时 / 并发：`project.yaml` → `agent.resource_limits`）
  → ffmpeg 编码
  → 输出: .agent/tmp/{scene}/final.mp4
```

## 使用方式

### 任意 Host Agent 直接使用（推荐）

MaCode 的所有工具都是独立 CLI，可被任何 Coding Agent（Claude Code、Cursor、Kimi 等）直接调用：

```bash
cd MaCode/

# Host Agent 直接调用标准工具
pipeline/render.sh scenes/01_test/
bin/macode inspect --grep "Circle"
bin/detect-hardware.sh
```

Host Agent 读取 `AGENTS.md` → `project.yaml` → `SOURCEMAP.md` 理解架构后，通过标准 Bash 工具调用 CLI，无需进入任何自定义 shell。

### 人类用户

```bash
bin/agent --check   # 检查项目配置
bin/agent --prompt  # 打印系统提示，复制给 LLM 使用

# 可选：进入带 safety-gate 的交互式 shell
bin/human-tools/agent-shell
```

## 开发阶段

| Phase | 内容 | 状态 |
|-------|------|------|
| 0 | 骨架 — 单场景渲染 | ✅ |
| 1 | 管道 — 多场景拼接 + ffmpeg 音频 | ✅ |
| 2 | 引擎抽象 — Motion Canvas 适配 | ✅ |
| 3 | Agent Harness — Git 流控制 + 安全门 | ✅ |
| 4 | 优化 — 缓存 + 并行 + 智能剪辑 | ✅ |
| 5 | 安全加固 — Coding Agent 接入 | ✅ |
| 6 | ManimGL + SOURCEMAP 硬化 + 语法防火墙 | ✅ |
| 7 | WSL2 GPU 加速 — Mesa D3D12 直通 | ✅ |
| 8 | Harness 2.0 — 编排/执行严格分离 + macode-run | ✅ |
| 9 | Harness 单机并发（本机并行、锁、macode-run） | ✅ |

详见 [`docs/progress.md`](docs/progress.md)。

## 本机并行与锁

并行渲染多场不同 scene 时请使用 `render-all` / composite 自带的线程池上限（`project.yaml` → `max_concurrent_scenes`）。Harness **不做**跨进程 Multi-Agent scene claim／排队（无 `.claimed_by`、无 exit 4/5）。

- **Check Report**：`macode check` 使用 POSIX `flock`，并发 check 同一 scene 不丢失 issue  
- **Git**：`agent-run.sh` 使用 `.agent/.git_lock` 串行化 commit  
- **端口**：MC dev server 通过 `bind()` 抢占空闲端口  
- **Stale**：`python3 bin/cleanup-stale.py [--dry-run] [--logs]` 将 dead-PID 的 `state.json` 标为 stalled，并可裁剪旧日志  

**Dashboard**（可选）：

```bash
curl -s http://localhost:3000/api/state | jq '.scenes[] | {name, status, phase}'
```

---

## 深度文档

| 文件 | 用途 |
|------|------|
| [`AGENTS.md`](AGENTS.md) | Host Agent 工作时的随手参考卡片（CLI 速查、引擎选型、反模式） |
| [`docs/architecture.md`](docs/architecture.md) | 系统架构 / 安全模型深度 / WSL2 调优 / 仪表盘 / 人类介入 / 并发模型 |
| [`docs/PRD-draft.md`](docs/PRD-draft.md) | 项目愿景、决策记录 |
| [`docs/refactor-todo.md`](docs/refactor-todo.md) | Sprint 任务跟踪 |
| [`docs/task-state-schema.md`](docs/task-state-schema.md) | 任务/帧反馈等 JSON 字段约定 |
| [`CHANGELOG.md`](CHANGELOG.md) | 变更历史 |
| [`tests/fixtures/scenes/README.md`](tests/fixtures/scenes/README.md) | 测试 fixture 命名约定 |

---

## 许可

MIT
