# MaCode — UNIX 原生的数学动画制作 Harness

> **Ma**th + **Code**. Make it work, then make it right, then make it fast.

MaCode 是一个 Bash-First 的数学动画 Agent 工作流系统。它不封装高级 API，而是提供一个**透明的、可被 `ls / cat / grep` 完全理解的文件系统环境**，让 Agent 通过 Bash 命令探索、组合、修复数学动画的每一个环节。

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

# 启动实时仪表盘（人类监控，Agent 零感知）
node bin/dashboard-server.mjs --port 3000
# → 浏览器打开 http://localhost:3000/
# → curl http://localhost:3000/api/state | jq .
```

> 开发/测试环境请使用 `bin/setup-dev.sh`（额外安装 pytest、ruff 并自动运行 smoke 测试）。

## 目录结构

```text
macode/
├── .macode/                # Agent 运行时状态（保留目录，不再存放 API Key）
├── .agent/                 # Agent 工作区（临时帧、缓存、日志）
│   ├── tmp/{scene}/        # 帧序列、渲染输出
│   ├── cache/              # 帧级缓存（按内容哈希寻址）
│   └── log/                # 全局渲染日志
├── engines/                # 渲染引擎适配层
│   ├── manim/              #   ManimCE（Python，默认 batch 引擎）
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
│   ├── render.sh           #   顶层路由（纯分发器，按 type 路由）
│   ├── render-scene.py     #   单场景编排器（validate → api-gate → cache → engine → deliver）
│   ├── composite-render.py #   Composite 编排器（segment 调度 → assemble）
│   ├── composite-unified-render.py  #   Composite-unified 编排器
│   ├── validate-manifest.py #   manifest 校验（执行层）
│   ├── concat.sh           #   帧序列 → MP4（执行层）
│   ├── add_audio.sh        #   音轨合成
│   ├── fade.sh             #   淡入淡出
│   ├── compress.sh         #   输出压缩
│   ├── preview.sh          #   快速预览
│   ├── smart-cut.sh        #   静默段自动剪辑
│   ├── thumbnail.sh        #   关键帧提取
│   ├── cache.sh            #   帧级缓存
│   └── deliver.sh          #   产物交付（.agent/tmp/ → output/）
├── bin/                    # 全局工具脚本
│   ├── setup.sh             #   项目初始化 — 用户版（不暴露测试依赖）
│   ├── setup-dev.sh         #   项目初始化 — 开发版（含测试框架 + 验证）
│   ├── agent                #   配置检查 + 系统提示生成
│   ├── agent-shell          #   人类用户可选交互式 shell（非 Host Agent 入口）
│   ├── macode               #   主入口 CLI（render / status / inspect）
│   ├── macode-run           #   统一进程生命周期管理器（Harness 2.0）
│   ├── api-gate.py          #   BLACKLIST 导入 + sandbox 危险调用扫描
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

每个引擎目录下有一份 `SOURCEMAP.md`，是 Agent 的**源码探索地图**：

- **WHITELIST**：安全的、值得阅读的 API 表面（P0/P1/P2 分级）
- **BLACKLIST**：陷阱路径（废弃 API、内部黑魔法、测试代码）
- **EXTENSION**：引擎支持但 MaCode 尚未接入的能力

Agent 通过 `macode inspect --grep <keyword>` 查询，渲染前 `api-gate.py` 自动拦截 BLACKLIST 导入。

### 场景契约 (manifest.json)

```json
{
  "engine": "manim",
  "duration": 10,
  "fps": 30,
  "resolution": [1920, 1080],
  "assets": ["assets/formula.tex"],
  "dependencies": ["scenes/00_title/manifest.json"]
}
```

## 配置

### 项目配置（`project.yaml`）

```yaml
defaults:
  engine: manim
  resolution: [1920, 1080]
  fps: 30
```

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

### Composite manifest 示例

```json
{
  "type": "composite",
  "segments": [
    {"id": "intro", "scene_dir": "shots/00_intro", "transition": {"type": "fade", "duration": 0.3}},
    {"id": "main", "scene_dir": "shots/01_main", "transition": {"type": "wipeleft", "duration": 0.5}},
    {"id": "outro", "scene_dir": "shots/02_outro"}
  ],
  "audio": {
    "tracks": [{"file": "assets/bg.mp3", "loop": true, "volume": 0.2, "fade_in": 0.5}]
  },
  "params": {"theme_color": "#1E90FF", "title_text": "讲座标题"}
}
```

### 双轨架构

| 模式 | manifest type | 特点 |
|------|--------------|------|
| **分轨合成** | `composite` | 独立渲染 + ffmpeg xfade 转场，可并行，状态不连续 |
| **统一渲染** | `composite-unified` | 单 Scene 实例顺序执行，状态连续 |

Segment 源码中通过 `os.environ["MACODE_PARAMS_JSON"]` 读取注入参数。

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

# 8. 交付到 output/ 目录
pipeline/deliver.sh scenes/02_fourier/

# 9. 多场景拼接 + 音频合成
pipeline/concat.sh output/*.mp4 output/lecture.mp4
pipeline/add_audio.sh output/lecture.mp4 assets/bgm.mp3 output/final.mp4
```

## 引擎与环境管理

| 引擎 | 语言 | 模式 | 状态 | 适用场景 |
|------|------|------|------|----------|
| ManimCE | Python | batch | **默认** | 3Blue1Brown 风格、LaTeX 公式、几何动画 |
| ManimGL | Python | interactive | 预览 | Grant Sanderson 原版，实时 OpenGL 交互 |
| Motion Canvas | TypeScript | batch | 备选 | 热重载迭代、Web 原生导出 |

### 环境隔离原则

- **Python**：由 `uv` 统一管理，在项目根目录创建 `.venv/` 虚拟环境。ManimCE 及所有 Python 依赖仅安装于此，绝不使用全局 `pip` 或 `conda`。
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

- `pre-commit`：拦截对 `bin/`、`engines/`、`pipeline/` 等基础设施的误修改；对 `scenes/` 的修改自动运行 fs-guard 边界检查。
- `pre-push`：推送前全量扫描所有场景的 `security-run.sh`（导入黑名单 + sandbox + 原语检测）。

**基础设施维护**：当你需要修改 `bin/`、`engines/` 等受保护目录时，pre-commit 会拒绝提交。这是设计行为 —— 请使用 `git commit --no-verify` 并确保修改经过人工 review。

## 安全模型

渲染前自动执行五层防御：

```
Host Agent 调用
  → 可选: bin/api-gate.py   (渲染前静态检查：BLACKLIST 导入 + sandbox 扫描)
  → pipeline/render.sh      (manifest 校验 → 引擎渲染 → api-gate → 缓存 → timeout)
  → 内置熔断: 帧数上限 10000 / 磁盘上限 50GB / 渲染超时 600s
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
| 9 | Multi-Agent 并发协调 — claim / flock / 端口原子分配 | ✅ |

详见 [`docs/progress.md`](docs/progress.md)。

## Multi-Agent 并发协调

MaCode 支持多个独立 Agent 实例安全并发地操作同一项目：

```bash
# Agent 1 负责 scene A（--no-review 跳过人工审查标记，适合自动化循环）
MACODE_AGENT_ID="agent-1" macode render scenes/01_test/ --no-review

# Agent 2 负责 scene B（同时进行）
MACODE_AGENT_ID="agent-2" macode render scenes/02_demo/ --no-review &
```

**机制**：
- **Scene Claim**：渲染前自动写入 `.agent/tmp/{scene}/.claimed_by`，其他 Agent 发现 claim 存在则跳过
- **全局并发限制**：受 `project.yaml` 的 `max_concurrent_scenes` 约束（默认 4），超限时自动排队
- **Check Report 锁**：`macode check` 使用 POSIX `flock`，并发 check 同一 scene 不丢失 issue
- **Git 锁**：`agent-run.sh` 的 `git commit` 使用 `.agent/.git_lock`，多 Agent 同时 commit 不冲突
- **端口原子分配**：MC dev server 使用 `bind()` 原子抢占端口，避免启动冲突
- **Stale 清理**：`python3 bin/cleanup-stale.py [--dry-run]` 定期清理 dead-PID 任务和过期 claim

**Dashboard 观测**：
```bash
curl -s http://localhost:3456/api/state | jq '.scenes[] | {name, status, agentId, claimedBy}'
curl -s http://localhost:3456/api/queue | jq .
```

---

## 许可

MIT
