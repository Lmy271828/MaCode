# MaCode Architecture Reference

> 深度参考文档。日常工作请先查 [`AGENTS.md`](../AGENTS.md)。
> 本文是 Host Agent 编写引擎适配器、安全策略、并发模型时的延伸阅读。

## 目录

1. [系统架构总览](#1-系统架构总览)
2. [安全模型深度参考](#2-安全模型深度参考)
3. [WSL2 运行环境调优](#3-wsl2-运行环境调优)
4. [实时仪表盘](#4-实时仪表盘)
5. [人类介入协议](#5-人类介入协议)
6. [并发与宿主模型](#6-并发与宿主模型)

---

## 1. 系统架构总览

### 1.1 目录结构（Agent 的"API 文档"）

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
│   ├── pre-commit           #   提交前拦截 protected 文件修改
│   └── pre-push             #   推送前 api-gate 导入检查
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

### 1.2 三层解耦（可迁移性的基石）

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

## 2. 安全模型

MaCode 采用**诚实轻量的安全策略**：渲染时通过 `api-gate.py` 拦截 BLACKLIST 导入，Git 层面通过 hooks 保护基础设施目录。我们不内建运行时沙箱——如果你需要隔离不可信代码，应在容器或独立用户中运行 Harness。

### 2.1 Git Hooks

Hooks 以版本化模板形式存在于 `.githooks/`，由 `bin/install-hooks.sh` 在 setup 时复制到 `.git/hooks/`：

```bash
# 安装/更新 hooks（首次 setup 或模板变更后运行）
bin/install-hooks.sh

# 验证 hooks 已安装且为最新
bin/install-hooks.sh --check
```

- **`pre-commit`**：拦截对 `engines/`、`bin/`、`pipeline/` 及根目录 `project.yaml`、`requirements.txt`、`package.json` 的暂存修改。
- **`pre-push`**：对所有可渲染场景运行 `api-gate.py` 导入检查。

> **注意**：`.githooks/` 目录本身不受 pre-commit 保护，因此 hooks 模板可以被正常更新而无需 `--no-verify`。

### 2.2 资源熔断

```bash
# 读取 project.yaml，无需 Host Agent 干预
# - 渲染超时：600s  （由 engines/*/scripts/render.sh 强制执行）
# - 全局并发上限：max_concurrent_scenes  （由 bin/render-all.sh 强制执行）
#
# 以下限制在 project.yaml 中声明，但当前未自动化强制执行：
# - 帧数上限：10000
# - 磁盘上限：50GB
#   （依赖 Host Agent 自觉遵守，或后续通过 render-scene.py 内置熔断实现）
```

---

## 3. WSL2 运行环境调优

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

## 4. 人类介入协议

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
        ├── reject         # 该 scene 被驳回
        └── human_override.json  # 该 scene 的覆盖决策
```

### 4.1 Host Agent 义务（每次执行动作前）
1. 检查 per-scene 信号（`.agent/signals/per-scene/{scene}/pause|abort`）— 存在则针对该 scene 暂停/退出
2. 回退检查全局信号（`.agent/signals/global/pause|abort`）— 存在则全部暂停/退出
3. 检查 `.agent/signals/human_override.json` — 存在则遵守覆盖决策
4. ~~检查 per-scene `review_needed`~~ — **已移除（P0-3）**；阻塞式审查机制已废弃，人类干预通过 `human_override.json` 直接进行

使用 `bin/signal-check.py` 统一查询：
```bash
# 查询所有信号（全局 + 全部 scene）
python3 bin/signal-check.py

# 只查询全局信号
python3 bin/signal-check.py --global-only

# 查询特定 scene 的信号
python3 bin/signal-check.py --scene 01_test
```

### 4.2 Host Agent 权利
1. 渲染完成后自动运行 check，生成 JSON 报告到 `.agent/check_reports/`
2. ~~发现严重问题时创建 `review_needed` 请求人类审核~~ — **已移除（P0-3）**；问题通过 check report 暴露，人类通过 `human_override.json` 干预
3. 读取 `@human:` 注释并优先处理

### 4.3 人类权利
1. 随时 `touch .agent/signals/global/pause` 暂停所有 Agent
2. 随时 `touch .agent/signals/per-scene/01_test/pause` 只暂停 scene 01_test
3. 随时直接编辑 `scenes/` 下的文件
4. 随时 `rm .agent/signals/per-scene/01_test/review_needed` 让特定 scene 继续

---

## 5. 并发与宿主模型

PRD 不包含跨进程 Multi-Agent：**不在 Harness 层做 scene claim、排队或 exit 4/5**。同一项目内若要并行渲染，请自行用外层编排（或通过 `render-all`/composite 的线程池在本机并行**不同目录**）。

仍保留的工程事实：

| 机制 | 用途 |
|------|------|
| **Check Report 锁** | POSIX `flock`，避免并行写同一检查报告 JSON |
| **Git 锁** | `agent-run.sh` / `.agent/.git_lock` 串行化 commit |
| **端口抢占** | 渲染前通过 `bind()` 分配空闲端口（非跨 Agent 协议）|

`project.yaml` 的 `max_concurrent_scenes` 仍可用于 **本机** `render-all` / composite 的并行上限，与已过期的「全局 claim 排队」语义无关。

### 6.1 Stale 状态清理

渲染进程崩溃后，`state.json` 可能长时间停留在 `running`。清理：

```bash
python3 bin/cleanup-stale.py --dry-run
python3 bin/cleanup-stale.py
```

可选 `--logs`：按保留策略裁剪 `.agent/log/*.log`。
