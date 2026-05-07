# MaCode 开发路线图

> **哲学声明**：先让程序工作，再考虑优化的事情。  
> *"We should forget about small efficiencies, say about 97% of the time: premature optimization is the root of all evil."* —— Donald Knuth
>
> **项目命名**：MaCode = Math + Code。简洁、可打字、无歧义。

---

## Phase 0：骨架 —— 让单个场景跑起来（Week 1）

**目标**：证明核心假设可行。一个 Agent 可以修改场景代码，通过 bash 调用渲染，输出视频文件。

### 0.1 必须完成
- [x] 创建目录结构（`engines/manim/`, `scenes/01_test/`, `pipeline/`, `.agent/tmp/`）。
- [x] 编写 `engines/manim/scripts/render.sh`：接收 `scene.py` + 输出目录，调用 `python -m manim` 输出帧序列。
- [x] 编写 `pipeline/render.sh`：读取 `manifest.json`，调用引擎渲染脚本。
- [x] 编写 `pipeline/concat.sh`：接收帧序列目录，调用 `ffmpeg` 编码为 MP4。
- [x] 编写一个最简单的测试场景 `scenes/01_test/manifest.json` + `scene.py`（画一个圆，持续 3 秒）。
- [x] Agent 可以通过 bash 成功运行：`pipeline/render.sh scenes/01_test/` 并在 `.agent/tmp/01_test/` 看到 `final.mp4`。

### 0.2 明确不做（抵抗诱惑）
- ❌ 不支持 Motion Canvas。
- ❌ 不写 `inspect.sh`，Agent 直接读源码。
- ❌ 不做 Git 流控制，Agent 手动 `git commit`。
- ❌ 不做资源熔断，相信 Agent 不会写死循环。
- ❌ 不优化缓存，每次全量渲染。
- ❌ 不处理音频（Phase 1 再引入 `ffmpeg` 音频合成）。
- ❌ 不实现 `project.yaml`，硬编码配置在脚本里。
- ❌ 不引入 `sox`，音频相关功能全部推迟到 Phase 1 用 `ffmpeg` 实现。

### 0.3 完成标准
```bash
$ ls scenes/01_test/
manifest.json  scene.py

$ pipeline/render.sh scenes/01_test/
[manim] Rendering scene.py...
[ffmpeg] Encoding frames to final.mp4...
Done: .agent/tmp/01_test/final.mp4

$ ffprobe -v error -show_entries format=duration -of \
    default=noprint_wrappers=1:nokey=1 .agent/tmp/01_test/final.mp4
3.000000
```

---

## Phase 1：管道 —— 连接场景与后处理（Week 2）

**目标**：让"场景 → 帧 → 视频 → 剪辑"的管道可组合，Agent 能用 bash 拼接多个场景。引入 ffmpeg 音频处理。

### 1.1 必须完成
- [x] 编写 `pipeline/add_audio.sh`：接收视频 + 音频文件，使用 `ffmpeg` 合成输出。
- [x] 编写 `pipeline/fade.sh`：使用 `ffmpeg afade / fade` 实现音视频淡入淡出。
- [x] 编写 `pipeline/preview.sh`：降分辨率 / 抽帧快速预览（用于 Agent 迭代调试）。
- [x] 编写 `pipeline/compress.sh`：CRF 28 快速压缩，用于生成社交媒体版本。
- [x] 实现 `scenes/` 目录的批量渲染：`bin/render-all.sh` 按序号遍历所有场景。
- [x] 帧序列必须物理保留在 `.agent/tmp/{scene}/frames/`，Agent 可逐帧检查。
- [x] 所有脚本将日志写入 `.agent/log/`，Agent 可用 `tail` 调试。
- [x] 验证 ffmpeg 音频生成功能：
  - `ffmpeg -f lavfi -i "sine=frequency=1000:duration=1"` 生成提示音
  - `ffmpeg -f lavfi -i anullsrc=r=48000:cl=stereo -t 5` 生成静音填充
  - `ffmpeg -i input.mp4 -af "afade=t=in:ss=0:d=0.5"` 音频淡入

### 1.2 明确不做
- ❌ 不做引擎抽象层，仍然只支持 ManimCE。
- ❌ 不做 `manifest.json` 的严格校验，Agent 手写 JSON。
- ❌ 不做 Git 自动化回滚，仍然手动。
- ❌ 不实现并行渲染，串行执行。
- ❌ 不引入 `sox` 或其他音频工具，ffmpeg 覆盖全部音频需求。

### 1.3 完成标准
```bash
$ bin/render-all.sh
[1/3] Rendering scenes/00_title/... OK
[2/3] Rendering scenes/01_intro/... OK
[3/3] Rendering scenes/02_fourier/... OK

$ pipeline/concat.sh scenes/*/output/final.mp4 output/lecture.mp4
$ ffprobe output/lecture.mp4 | grep Duration
Duration: 00:05:30.00

$ pipeline/add_audio.sh output/lecture.mp4 assets/background.mp3 output/lecture_with_music.mp4
$ ffprobe output/lecture_with_music.mp4 2>&1 | grep Stream | grep Audio
Stream #0:1: audio: aac ...
```

---

## Phase 2：引擎抽象 —— 支持第二个引擎（Week 3）

**目标**：验证"引擎无关"架构。引入 Motion Canvas，证明迁移成本极低。

### 2.1 必须完成
- [x] 设计并固化 `manifest.json` 契约格式（引擎类型、时长、分辨率、资产列表）。
- [x] 重构 `pipeline/render.sh`：读取 `manifest.json` 中的 `engine` 字段，分发到 `engines/<engine>/scripts/render.sh`。
- [x] 创建 `engines/motion_canvas/` 适配层：
  - `scripts/render.sh`：调用 Node.js headless 渲染脚本输出帧（含占位回退）。
  - `src/templates/scene_base.tsx`：基础场景模板。
- [x] 创建 `engines/*/scripts/inspect.sh`：打印该引擎可用的模板与工具函数。
- [x] 编写迁移示例：将 Phase 0 的 `01_test` 从 Manim 迁移到 Motion Canvas，只修改 `manifest.json` + 重写 `scene.tsx`。

### 2.2 明确不做
- ❌ 不做自动迁移工具，Agent 手动重写场景文件。
- ❌ 不统一 Mobject API（如让 Manim 的 `Circle` 和 Motion Canvas 的 `Circle` 行为完全一致），统一只在 manifest 语义层。
- ❌ 不做引擎版本管理，假设环境已预装。
- ❌ 不引入新音频工具，继续用 ffmpeg 处理全部音频。

### 2.3 完成标准
```bash
$ cat scenes/01_test/manifest.json | jq .engine
"motion_canvas"

$ pipeline/render.sh scenes/01_test/
[motion_canvas] Building scene.tsx...
[ffmpeg] Encoding...
Done: .agent/tmp/01_test/final.mp4

# 视频时长与 Manim 版本一致，内容等价
$ diff <(ffprobe manim_version.mp4) <(ffprobe motion_canvas_version.mp4)
# 仅编码器元数据差异，时长/分辨率/帧率一致
```

---

## Phase 3：Agent Harness —— Git 流控制与安全（Week 4）

**目标**：让 Agent 可以安全地自主迭代，错误可一键回滚。

### 3.1 必须完成
- [x] 编写 `bin/macode`：主入口 CLI，支持 `macode render <scene>`、`macode status`、`macode undo`。
- [x] 编写 `bin/agent-shell`：Agent 的默认 shell 入口，预装 PATH 与别名。
- [x] 编写 `bin/agent-run.sh`：包装器，实现 Git 原子操作协议：
  - 任务前：`git stash` + `git checkout -b agent/task_id`
  - 任务后：成功则 `commit + merge --no-ff`，失败则 `checkout - + branch -D`
- [x] 编写 `bin/safety-gate.sh`：命令白名单拦截器，解析 Agent 提交的 bash 命令，拦截非白名单工具。
- [x] 编写 `bin/discover`：交互式项目结构探索脚本，Agent 迷路时调用。
- [x] 引入 `project.yaml`：全局配置（默认引擎、分辨率、安全白名单、资源限制）。
- [x] 实现资源熔断：渲染前检查帧数 / 磁盘 / 时间上限。

### 3.2 明确不做
- ❌ 不做复杂的权限系统（RBAC/OAuth），单用户本地运行。
- ❌ 不做分布式渲染，单机运行。
- ❌ 不做 Web UI，纯 CLI。
- ❌ 不优化 Git 性能（大文件用 `.gitignore` 排除，不引入 LFS）。
- ❌ 不引入 `sox` 或其他音频工具。

### 3.3 完成标准
```bash
$ bin/agent-run.sh "sed -i 's/blue/red/g' scenes/01_test/scene.py"
[agent] Stash current state...
[agent] Running command...
[agent] Command failed with exit code 1. Auto-rollback...
[agent] State restored to pre-task.

$ git log --oneline -5
abc1234 merge: agent_001 — sed color change
9f8e7d2 agent: agent_001 — sed color change
def4567 pre-task stash
# 失败的任务未污染历史

$ macode status
Project: MaCode
Default engine: manim
Scenes: 3 (1 dirty)
Last render: scenes/01_test/ — 3.0s @ 1920x1080
```

---

## Phase 4：优化 —— 缓存、并行与压缩（Week 5+, 2026-05-04 启动）

**目标**：在"工作"被证明之后，让系统更快、更省资源。

### 4.1 缓存层（先测量，再优化）
- [x] 实现帧级缓存：基于 `scene.py` + `manifest.json` 内容哈希（sha256sum/md5sum），避免重复渲染未变更的帧。
- [x] 缓存目录：`.agent/cache/{scene_hash}/frames/`，同时保存 manifest 与源码副本便于审计。
- [ ] 使用 `just` 替代裸 bash 脚本，利用文件时间戳判断过期。→ **跳过**：`just` 未安装在当前环境，纯 bash + 内容哈希已满足需求。

### 4.2 并行渲染
- [x] 场景级并行：依赖拓扑排序 + 层级调度，独立场景按 `max_concurrent_scenes` 并发渲染。
- [ ] 帧级并行（谨慎）：对无状态引擎，尝试 `seq 0 300 | xargs -P4 -I{} manim --frame {}`。→ **跳过**：需要先测量单帧渲染开销，当前阶段无性能数据支撑。

### 4.3 智能剪辑
- [x] 实现 `pipeline/smart-cut.sh`：基于 `ffprobe silencedetect` 检测静默段，ffmpeg filtergraph 精确切割非静默段拼接。
- [x] 实现 `pipeline/thumbnail.sh`：支持 mid / N 帧均匀 / time=MM:SS / interval=N 四种模式提取关键帧。

### 4.4 明确不做（直到有明确需求）
- ❌ 不引入数据库（SQLite/Redis）管理缓存，继续用文件系统 + 哈希。
- ❌ 不做 GPU 渲染优化（如 CUDA 加速），保持 CPU 兼容。
- ❌ 不做实时预览服务器，继续用 `pipeline/preview.sh` 生成低分辨率文件。
- ❌ 不引入 `sox` 或其他音频工具，ffmpeg 已覆盖全部需求。

---

## Phase 5：安全加固 —— Coding Agent 接入（2026-05-04 ~ 2026-05-05）

**目标**：在 Phase 0-4 功能就绪后，系统性审计并修复安全漏洞，使 Coding Agent 可安全自主操作。

### 5.1 P0 必须修复（最低防线）
- [x] 接入 `safety-gate.sh`：agent-shell 通过 READLINE Enter-key 拦截 + `bin/gate` 包装器，所有命令经白名单检查。
- [x] 接入 `agent-run.sh`：`macode render` 默认包裹 Git 原子操作（成功 commit 场景变更，失败回滚）。
- [x] 渲染超时强制执行：manim 调用包装在 `timeout` 中，读取 `project.yaml` 的 `max_render_time_sec`（默认 600s）。
- [x] 保护 `.macode/`：blocked_patterns 拦截 `cat .macode/*` 等敏感文件读取。
- [x] 收缩命令白名单：从 `project.yaml` 移除 `bash`、`python3`、`node`、`npm`、`npx`。

### 5.2 P1 应当修复（纵深防御）
- [x] Python sandbox：`api-gate.py` 新增 16 种危险调用模式检测（subprocess、os.system、socket、requests、shutil.rmtree、__import__ 等）。
- [x] manifest.json 校验：`pipeline/render.sh` 渲染前验证必填字段、引擎枚举、fps > 0、resolution 格式。
- [x] Git 保护：blocked_patterns 拦截 `git push --force`、`git reset --hard`、`git clean -f`。

### 5.3 Coding Agent 入口
- [x] 编写 `bin/agent`：配置检查 + 系统提示生成 + 安全 agent-shell 启动。
- [x] 修复 `agent-shell` 尾部 bug：原来 `exec bash --rcfile` 丢弃了全部环境变量，改为生成完整 rcfile。

### 5.4 安全态势验证

| 测试用例 | 预期 | 结果 |
|----------|------|------|
| `git push --force` | 拦截 | ✓ REJECTED |
| `cat .macode/*` | 拦截 | ✓ REJECTED |
| `curl evil.com` | 拦截 | ✓ REJECTED |
| `pip install requests` | 拦截 | ✓ REJECTED |
| `import subprocess` (scene.py) | 拦截 | ✓ API_GATE_VIOLATIONS |
| `os.system('ls')` (scene.py) | 拦截 | ✓ SANDBOX violation |
| `git status` | 放行 | ✓ ALLOWED |
| `ffmpeg -i in.mp4 out.mp4` | 放行 | ✓ ALLOWED |
| 畸形 manifest.json | 拦截 | ✓ FAILED |

### 5.5 明确不做
- ❌ 不做 Python 完整沙箱（容器/虚拟机），依赖多层静态检查 + timeout 熔断已足够。
- ❌ 不做 Claude Code 插件化（skill/hook），当前通过 `CLAUDE.md` + `agent-shell` 协作已满足需求。

---

## 附录：决策日志

| 日期 | 决策 | 理由 |
|------|------|------|
| Day 0 | 项目命名为 MaCode | Math + Code，简洁、可打字、无歧义，符合 UNIX 短命令传统 |
| Day 0 | 选择 ManimCE 作为 Phase 0 唯一引擎 | 生态最成熟，Agent 训练数据丰富，降低 Phase 0 失败风险 |
| Day 0 | 推迟 Motion Canvas 到 Phase 2 | 避免早期多引擎导致架构腐化，先验证单引擎管道 |
| Day 0 | 推迟 Git 自动化到 Phase 3 | Phase 0/1 由人类开发者手动控制，减少调试复杂度 |
| Day 0 | 使用 `manifest.json` 而非数据库 | 符合 UNIX 文本流原则，`jq` 即可处理，无需 SQL |
| Day 0 | 使用 `Just` 而非 `Make` | 语法现代，Agent 易读易改，但底层仍是文件时间戳 |
| Day 0 | 放弃 SoX，音频统一由 ffmpeg 处理 | Windows 下 SoX 管道不可靠、MP3 支持缺失、PowerShell 集成差；ffmpeg 跨平台一致 |
| 2026-05-04 | Phase 3 Agent Harness 完成 | macode CLI、agent-run.sh、safety-gate.sh、project.yaml 全部就绪 |
| 2026-05-04 | 启动 Phase 4 优化阶段 | 帧级缓存 → 并行渲染 → 智能剪辑 |
| 2026-05-04 | 帧级缓存用 sha256sum 实现 | `just` 未安装；内容哈希比文件时间戳更准确 |
| 2026-05-04 | 并行渲染用拓扑排序调度 | 读取 manifest.json 依赖构建 DAG，层级并行 |
| 2026-05-04 | 跳过帧级并行 | 需先测量单帧渲染开销，无性能数据前暂不实现 |
| 2026-05-04 | smart-cut 无音频时 passthrough | 无音频视频直接复制，避免破坏纯视觉内容 |
| 2026-05-04 | 启动安全审计 | safety-gate 和 agent-run 存在但从未被调用，属于死代码 |
| 2026-05-05 | safety-gate 改为主命令检查 | 原来逐词检查导致 `git status` 被拒绝（status 不在白名单），改为只检查每段第一个词 |
| 2026-05-05 | 修复 agent-shell 丢失环境的 bug | `exec bash --rcfile` 用了极简 rcfile，所有 PATH/别名/env 被丢弃 |
| 2026-05-05 | api-gate 新增 sandbox 扫描 | 除 BLACKLIST 导入外，增加 16 种危险 Python 调用检测 |
| 2026-05-05 | 不做 Claude Code 插件化 | 当前 `CLAUDE.md` + `agent-shell` 协作已满足 Claude Code 作为 Coding Agent 的需求 |
| 2026-05-05 | Phase 5 完成，MaCode v0.1.0 可安全接入 Coding Agent | 五层防御：safety-gate → agent-run → manifest 校验 → api-gate + sandbox → timeout 熔断 |

---

*路线图版本：v0.3*  
*哲学：Make it work → Make it right → Make it fast*  
*当前阶段：Phase 5 完成，v0.1.0 就绪 —— 2026-05-05*

---

## Phase 6：ManimGL 引入 & SOURCEMAP 协议硬化（2026-05-07）

**目标**：引入 ManimGL（Grant Sanderson 原版）作为 interactive preview 引擎；将 SOURCEMAP 从 Markdown 强化为 "Markdown 源码 + JSON 机器接口" 的严格协议。

### 6.1 今日已完成
- [x] 创建 `engines/manimgl/` 完整适配层（`engine.conf` + `SOURCEMAP.md` + `scripts/{render,inspect,validate_sourcemap}.sh` + `src/templates/scene_base.py`）
- [x] `pipeline/render.sh` 引擎无关化：通过 `engines/*/engine.conf` 动态枚举，支持 `mode: interactive` 分支（跳过 concat/cache，touch placeholder）
- [x] `engine.conf` 升级接口：新增 `compatibility`、`cli_signature`、`output_pattern` 字段
- [x] SOURCEMAP 协议硬化：
  - `bin/sourcemap-lint.py`：Markdown schema 校验器（3 节结构、优先级枚举、WHITELIST ≤20、危险模式检测）
  - `bin/sourcemap-sync.py`：内容哈希替代 mtime，自动 lint 前置，输出 `.agent/context/{engine}_sourcemap.json`
  - 所有消费者（`macode inspect`、`agent-shell`、`engines/*/scripts/inspect.sh`）改读 JSON，不再直接 awk Markdown
  - `validate_sourcemap.sh` 移除危险 `eval`，改用安全 Python 命令提取
- [x] Motion Canvas WHITELIST 精简：28 → 14 行，满足 ≤20 规则
- [x] `macode` CLI 扩展：`engine` 状态、`migrate` 占位、`sourcemap validate` 子命令
- [x] AUDIO_SYNC 实现：`pipeline/audio-analyze.sh` + `engines/*/src/utils/audio_sync.{py,ts}` + `scenes/03_audio_demo/`
- [x] `pipeline/concat.sh` FPS 参数化（原硬编码 30）
- [x] **ADAPTER_SCENE_BASE — ManimCE 场景基类**：
  - `engines/manim/src/templates/scene_base.py`：`MaCodeScene(MovingCameraScene)`
  - 功能：适配层路径自动注入（告别手动 `sys.path.insert`）、开场/结尾动画钩子、`focus_on()` / `zoom_to_fit()` 相机封装、`load_audio_sync()` 便利方法
  - `engines/manim/scripts/render.sh`：新增 `PYTHONPATH` 注入，使场景可直接 `from templates.scene_base import MaCodeScene`
  - 验证场景：`scenes/04_base_demo/`（203 帧，11 动画，api-gate 通过）
- [x] **ADAPTER_LATEX_HELPER — LaTeX 辅助工具**：
  - `engines/manim/src/utils/latex_helper.py`
  - 核心功能：
    - `ChineseMathTex` / `ChineseTex`：开箱即用的中文 LaTeX（xelatex + ctex）
    - `math()` 工厂函数：`math("E=mc^2", color=RED, scale=1.5)` 一步生成带样式公式
    - `cases()` / `matrix()` / `align_eqns()` / `integral()` / `derivative()`：常见数学结构工厂
    - `precompile_formulas()`：批量预编译加速
    - `diagnose_tex_error()`：友好错误诊断
  - 验证场景：`scenes/05_latex_demo/`（302 帧，17 动画，api-gate 通过）

### 6.2 今日问题（已解决）
| 问题 | 状态 | 详情 |
|------|------|------|
| ManimGL 安装失败 | ✅ 已解决 | `uv pip install manimgl` 后台 900s 超时完成；额外修复 Python 3.13 兼容性问题：setuptools 82 移除 pkg_resources → 降级至 70.3.0；pydub 依赖 audioop → 安装 `audioop-lts` |
| render.sh interactive 占位回退 | ✅ 已验证 | HEADLESS=1 时正确生成 30 帧 1920x1080 placeholder PNG；非 HEADLESS 时成功启动 `python -m manimlib` 并显示交互提示 |

### 6.3 实际解决方案
- **采用方案 A（延长超时 900s + 后台异步）**：安装成功，`.venv-manimgl/` 最终 399M
- **附加修复**：
  - `setuptools==70.3.0`：manimlib 1.7.2 仍依赖 `pkg_resources`，setuptools 82 已移除该模块
  - `audioop-lts==0.2.2`：Python 3.13 移除 stdlib `audioop`，pydub 需要此兼容包

### 6.4 验收结果（全部通过）
- [x] **P0** 完成 ManimGL 安装 — `manimlib` 1.7.2 导入成功
- [x] **P0** `validate_sourcemap.sh` — WHITELIST 15/15 路径全部命中；BLACKLIST 正确识别已移除项（`stream_starter.py` 在 1.7.2 中已删除）；PASS 16 / FAIL 0 / SKIP 16
- [x] **P0** `inspect.sh` — 正确输出 WHITELIST/BLACKLIST/EXTENSION 三段，实际版本 v1.7.2 与 SOURCEMAP 静态版本差异已记录
- [x] **P1** `render.sh` HEADLESS fallback — 30 帧 placeholder PNG 生成正确（1920×1080，darkblue 背景 + 文字标注）
- [x] **P1** `render.sh` interactive preview — `python -m manimlib` 启动成功，输出交互提示（`d/f/z` 键交互，`command+q/esc` 退出）
- [x] **P1** 全引擎回归 — `sourcemap-lint` + `sourcemap-sync` 对 manim / manimgl / motion_canvas 全部通过

### 6.5 决策记录
| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-05-07 | SOURCEMAP "Markdown 源码 + JSON 机器接口" | 原 awk 直接解析 Markdown 太脆弱，Agent 消费 JSON 更可靠；lint 前置防止脏数据进入上下文 |
| 2026-05-07 | ManimGL 定位为 interactive-only | ManimGL 输出的是实时 OpenGL 窗口，不生成帧序列；与 batch 引擎（ManimCE/Motion Canvas）互补，形成 "开发-生产" 双轨 |
| 2026-05-07 | 各引擎完全隔离虚拟环境 | ManimCE (`manim`) 与 ManimGL (`manimlib`) 命名空间冲突，共享环境会导致导入混乱 |
| 2026-05-07 | `render.sh` interactive 模式跳过 concat/cache | interactive 不产生帧序列，concat.sh 和 cache.sh 的假设（PNG 帧目录）不成立；统一在 render.sh 层面按 mode 分支 |
| 2026-05-07 | 启动 "语法防火墙" 架构 | Agent 不应直接写嵌套语法（LaTeX/GLSL/ffmpeg filtergraph/复杂正则）；三层防御：辅助层 + 语法门禁 + SOURCEMAP REDIRECT |
| 2026-05-07 | ffmpeg_builder.py + audio_builder.py | 流式 API 生成 ffmpeg 命令，消除手写 `-vf "fade=..."` 字符串拼接错误 |
| 2026-05-07 | pattern_helper.py + timeline_helper.py | 工厂模式生成正则/时间轴，消除手写 60+ 字符 regex 和 CSV 解析循环 |
| 2026-05-07 | api-gate SYNTAX_GATE | 渲染前静态检测：手写 ffmpeg filtergraph / LaTeX 环境 / GLSL / 复杂正则 → 拦截并提示改用工厂函数 |
| 2026-05-07 | SOURCEMAP REDIRECT 段 | 所有引擎 SOURCEMAP.md 新增 REDIRECT 段，inspect.sh 实时提示常见误区纠正 |
| 2026-05-07 | dry-run.py | 预渲染快速验证：LaTeX 预编译 + ffmpeg filtergraph 1 帧验证 + Python 语法/导入检查 |
| 2026-05-07 | shader_builder.py | 节点图 API 生成 GLSL（noise/gradient/colorize/oscillate），消除手写 `void main() { ... }` |
| 2026-05-07 | ManimGL/MC 适配层同步 | 将 manim 的 7 个 utils 模块同步到 manimgl；将 3 个 TS 模块同步到 motion_canvas |
| 2026-05-07 | GPU/CPU 自适应渲染后端 | 项目初始化时自动检测硬件（GPU/驱动/OpenGL），自适应选择 gpu / cpu / headless 三层后端 |
| 2026-05-07 | `bin/detect-hardware.sh` | 检测 GPU 型号、驱动版本、CUDA、OpenGL renderer（glxinfo + pyglet 双备用）、Vulkan、EGL/OSMesa |
| 2026-05-07 | `bin/select-backend.sh` | 读取硬件画像，输出 gpu/cpu/headless；支持 `--print` / `--env` 模式 |
| 2026-05-07 | `shader_backend.py` + `shader_builder.py` 后端适配 | GPU 后端生成 `#version 430` + Simplex noise；CPU 后端生成 `#version 330` + hash noise；auto-detect 从硬件画像 |
| 2026-05-07 | `scenes/07_shader_demo/` | ManimGL 场景验证 shader_builder 端到端：从硬件画像读取 → 生成 GLSL → 保存文件 → 渲染 |
| 2026-05-07 | `setup.sh` / `render.sh` 后端感知更新 | 渲染前自动设置 `LIBGL_ALWAYS_SOFTWARE=1`（cpu 后端）或 placeholder（headless）；`MACODE_HEADLESS=1` 保留为覆盖开关 |

---

## Phase 7：WSL2 GPU 加速 — Mesa D3D12 直通（2026-05-07）

**目标**：解决 WSL2 下 OpenGL 只能走 llvmpipe（CPU 软件渲染）的问题，通过 Mesa 的 D3D12 后端利用 WSL2 已透传的 DirectX 12 库调用 NVIDIA GPU。

### 7.1 问题分析

| 现象 | 根因 |
|------|------|
| `nvidia-smi` 显示 RTX 5060 | ✅ CUDA 透传正常 |
| OpenGL renderer = `llvmpipe` | ❌ Linux 端缺少 NVIDIA 专有 OpenGL 驱动 (`libGLX_nvidia.so`) |
| `/usr/share/glvnd/egl_vendor.d/` 只有 `50_mesa.json` | Mesa 是唯一 GL vendor，WSL2 不暴露 NVIDIA OpenGL ICD |

### 7.2 方案A：Mesa D3D12 后端（已实施）

**原理**：Mesa 的 `d3d12_dri.so` 将 OpenGL 调用转译为 DirectX 12，WSL2 的 `/usr/lib/wsl/lib/libd3d12.so` 将 DX12 转发到 Windows 主机的 NVIDIA 驱动。

```
OpenGL app → Mesa (d3d12_dri.so) → D3D12 (WSL2) → DX12 (Windows) → NVIDIA RTX 5060
```

**环境变量**：
```bash
export GALLIUM_DRIVER=d3d12
export LIBGL_ALWAYS_SOFTWARE=0
export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
```

### 7.3 后端层级扩展

原有：`gpu` → `cpu` → `headless`

新层级：`gpu` → `d3d12` → `cpu` → `headless`

| 后端 | 条件 | GLSL | 适用场景 |
|------|------|------|----------|
| `gpu` | 原生 GPU OpenGL（专有驱动）| `#version 430` + simplex | Linux 裸机 / 云 GPU 实例 |
| `d3d12` | Mesa D3D12 → DX12 → GPU | `#version 430` + simplex | **WSL2（当前环境）** |
| `cpu` | Mesa llvmpipe / softpipe | `#version 330` + hash | 无 GPU / 强制软件渲染 |
| `headless` | 无 OpenGL | — | 纯占位帧 / CI 环境 |

### 7.4 修改清单

- [x] `bin/detect-hardware.sh` — 新增 D3D12 探测：检测 `d3d12_dri.so` → 用 `GALLIUM_DRIVER=d3d12` 运行 pyglet → 识别 `D3D12 (NVIDIA ...)` renderer → JSON 新增 `d3d12` 字段
- [x] `bin/select-backend.sh` — 透传 `d3d12`（无需改动，已有字段读取机制兼容）
- [x] `engines/manimgl/src/utils/shader_backend.py` — 新增 `Backend.D3D12`，`glsl_version=#version 430`，`noise_impl=simplex`
- [x] `engines/manimgl/scripts/render.sh` — `d3d12` 分支注入 `GALLIUM_DRIVER=d3d12` + `MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA`
- [x] `engines/manim/scripts/render.sh` — 同上 D3D12 环境变量注入

### 7.5 验收结果

| 检查项 | 结果 |
|--------|------|
| `detect-hardware.sh` 输出 | `Backend: d3d12` |
| `select-backend.sh` 输出 | `d3d12` |
| OpenGL renderer | `D3D12 (NVIDIA GeForce RTX 5060 Laptop GPU)` |
| OpenGL version | `4.6`（从 llvmpipe 的 4.5 提升） |
| `shader_backend.py` | `Backend.D3D12` → `#version 430` / `simplex` |
| ManimCE 渲染测试 | 90 帧 Circle 场景成功，环境变量注入正确 |

### 7.6 决策记录

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-05-07 | WSL2 OpenGL llvmpipe 根因确认 | NVIDIA 只透传 CUDA/ML 库到 WSL2，不暴露 OpenGL 用户态驱动；Mesa 是唯一 GL vendor |
| 2026-05-07 | 选择方案 A（Mesa D3D12）而非方案 C（Windows 原生） | 方案 C 需重写全部 bash 管道为 PowerShell，破坏 MaCode Bash-First 架构；方案 A 只需注入环境变量 |
| 2026-05-07 | 后端层级扩展为 4 级 | `d3d12` 是 GPU 加速（非软件渲染），但不同于原生 `gpu`（专有驱动），需要独立层级以区分 GLSL 特性集 |
| 2026-05-07 | `MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA` | 系统有双 GPU（Intel Arc 140T + NVIDIA RTX 5060），默认 D3D12 可能选 Intel；强制 NVIDIA 确保最优性能 |

---

## 附录：问题-解决方案回顾（本次对话周期：2026-05-07）

> 以下记录按 **问题 → 分析 → 解决方案 → 是否违背初心** 的格式整理，覆盖 Phase 6 与 Phase 7 的全部重大修改。

### P1：ManimGL 与 ManimCE 导入冲突

**问题**：`uv pip install manimgl` 后，`from manimlib import *` 与 `from manim import *` 在同一 Python 环境中相互污染，导致 `Scene` 类来源混乱，Agent 无法判断该用哪个 API。

**分析**：`manim`（社区版）和 `manimlib`（Grant 原版）都定义了 `Scene`、`Mobject`、`config` 等同名符号，但 API 完全不兼容。共享环境等于强迫 Agent 同时理解两套冲突的命名空间。

**解决方案**：**完全隔离虚拟环境**。`.venv/` 只装 ManimCE，`.venv-manimgl/` 只装 ManimGL。`engines/manim/scripts/render.sh` 和 `engines/manimgl/scripts/render.sh` 分别调用各自的 Python 解释器，永不相交。

**违背初心？** 否。符合"引擎无关"原则——引擎隔离是架构设计的核心，虚拟环境隔离只是实现手段，manifest.json 的 `engine` 字段仍然是唯一切换点。

---

### P2：SOURCEMAP 被 Agent 误读或消费不一致

**问题**：`SOURCEMAP.md` 是人写的 Markdown，但 Agent 和消费者（`inspect.sh`、`macode inspect`、`api-gate.py`）用 `grep`/`awk`/`sed` 直接解析，导致：
- Markdown 格式微调就破坏解析逻辑
- 消费者代码散落各处，维护困难
- 没有校验机制，脏数据容易进入上下文

**分析**：Markdown 是给人看的，机器消费需要结构化数据。但引入数据库或 YAML 会增加复杂度，违背 UNIX 文本流原则。

**解决方案**：**"Markdown 源码 + JSON 机器接口"双层协议**：
- 人写 Markdown（`engines/*/SOURCEMAP.md`）
- `bin/sourcemap-lint.py` 校验 schema（3 节结构、优先级枚举、WHITELIST ≤20）
- `bin/sourcemap-sync.py` 将校验通过的 Markdown 转写为 `.agent/context/{engine}_sourcemap.json`
- 所有消费者统一读 JSON，不再直接解析 Markdown

**违背初心？** 否。JSON 仍是文本流，`jq` 即可处理；lint 前置保证数据质量；没有引入数据库或复杂状态管理。

---

### P3：Agent 手写嵌套语法导致运行时错误

**问题**：Agent 生成的场景代码中频繁出现：
- 手写 ffmpeg `-vf "fade=..."` filtergraph（引号嵌套错误）
- 手写 `\begin{cases}...\end{cases}`（与 Manim 的 `Tex`/`MathTex` 转义规则冲突）
- 手写 GLSL `void main() { ... }`（语法错误、版本不匹配）
- 手写 `re.compile(r'...60+ 字符...')`（可读性差、维护难）

**分析**：Agent 擅长调用函数，不擅长写字符串。嵌套语法（LaTeX/GLSL/ffmpeg/正则）的引号、转义、版本差异是错误高发区。

**解决方案**：**三层语法防火墙**：
1. **Helper 层** — 工厂函数消除手写字符串：
   - `ffmpeg_builder.py` / `audio_builder.py`：流式 API 生成 ffmpeg 命令
   - `latex_helper.py`：`cases()` / `matrix()` / `align_eqns()` / `integral()` / `derivative()`
   - `shader_builder.py`：节点图 API 生成 GLSL（noise/gradient/colorize/oscillate）
   - `pattern_helper.py` / `timeline_helper.py`：工厂模式生成正则/时间轴
2. **Gate 层** — `api-gate.py` 新增 `SYNTAX_GATE`：渲染前静态扫描，发现手写嵌套语法即拦截并提示改用工厂函数
3. **Redirect 层** — `SOURCEMAP.md` 新增 REDIRECT 段，`inspect.sh` 实时提示常见误区

**违背初心？** 否。所有 helper 都是纯 Python 工厂函数，无外部依赖；gate 是静态文本扫描，不引入运行时沙箱；Agent 仍然只写 Python 代码，只是从"写字符串"变成"调函数"。

---

### P4：场景代码重复写入 `sys.path.insert`

**问题**：每个 `scene.py` 开头都要写 `import sys; sys.path.insert(0, '../../engines/manim/src')` 才能引用适配层工具，路径深度随场景目录层级变化，容易写错。

**分析**：这是 Python 模块路径问题，但 Agent 不应该关心文件系统的相对路径。

**解决方案**：**`render.sh` 统一注入 `PYTHONPATH`**。引擎渲染脚本在调用 `python -m manim` 前，自动将 `engines/{engine}/src` 加入 `PYTHONPATH`，场景代码可直接 `from templates.scene_base import MaCodeScene`、`from utils.latex_helper import math`。

**违背初心？** 否。环境变量注入是标准 UNIX 做法；场景代码更简洁，Agent 只需关注动画逻辑。

---

### P5：WSL2 有 NVIDIA GPU 但 OpenGL 走 llvmpipe（CPU 渲染）

**问题**：`nvidia-smi` 显示 RTX 5060，但 `glxinfo`/pyglet 返回 `Mesa llvmpipe`（纯 CPU 软件光栅化），渲染极慢。

**分析**：
- WSL2 透传了 CUDA 库（`libcuda.so`）和 NVML（`libnvidia-ml.so`）
- 但 **没有透传 NVIDIA 的 OpenGL 用户态驱动**（`libGLX_nvidia.so`、`libEGL_nvidia.so`）
- Linux 端 GLVND 只有 Mesa 的 `50_mesa.json`，OpenGL 只能走 Mesa
- Mesa 的默认 DRI 驱动在 WSL2 下是 llvmpipe（软件渲染器）

**解决方案**：**方案 A — Mesa D3D12 后端**（而非方案 C — Windows 原生）：
- Mesa 提供 `d3d12_dri.so`，将 OpenGL 转译为 DirectX 12
- WSL2 已透传 `libd3d12.so`（在 `/usr/lib/wsl/lib/`，已注册到 ld.so）
- 设置 `GALLIUM_DRIVER=d3d12` + `MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA`
- OpenGL renderer 从 `llvmpipe` 变为 `D3D12 (NVIDIA GeForce RTX 5060 Laptop GPU)`
- 后端层级扩展：`gpu` → `d3d12` → `cpu` → `headless`

**违背初心？** 否。
- 方案 C（Windows 原生）会要求重写全部 bash 管道为 PowerShell，破坏 **Bash-First** 架构，因此被拒绝
- 方案 A 只需在 `render.sh` 中注入 3 个环境变量，不改变任何架构假设
- `detect-hardware.sh` 仍是纯 bash + Python 探测，输出 JSON 文本流
- 符合 **Make it work → Make it right → Make it fast**：先让 llvmpipe 工作，再识别根因，最后用 D3D12 加速

---

### P6：场景基类代码重复、相机操作不一致

**问题**：每个场景都重复写 `self.camera.frame.move_to()`、`self.camera.frame.set_width()`，相机聚焦逻辑不统一，Agent 经常写错坐标。

**分析**：相机操作是高频需求，应该封装为语义化 API。

**解决方案**：**`MaCodeScene(MovingCameraScene)` 基类**：
- `focus_on(mobject, buff=0.5)` — 自动将相机移到目标并调整尺寸
- `zoom_to_fit(group, margin=0.8)` — 让一组对象恰好充满画面
- `load_audio_sync(audio_file)` — 自动解析 `.audio_sync.json` 并绑定时间轴
- `setup()` / `teardown()` 钩子 — 统一开场/结尾动画

**违背初心？** 否。基类是 Python 的常规抽象，无外部依赖；Agent 写更少的代码，错误更少。

---

### P7：中文 LaTeX 反复配置失败

**问题**：Agent 写 `MathTex("中文")` 反复报错，因为默认 LaTeX 引擎不支持中文，需要手动配置 `tex_template` 的 `xelatex` + `ctex`。

**分析**：中文支持是东亚用户的刚需，但 Agent 不具备 LaTeX 发行版知识，容易在模板配置上卡住。

**解决方案**：**`latex_helper.py` 开箱即用**：
- `ChineseMathTex` / `ChineseTex` — 预配置 xelatex + ctex 模板
- `math("公式", color=RED, scale=1.5)` — 一步生成带样式公式
- `precompile_formulas()` — 批量预编译加速
- `diagnose_tex_error()` — 将 LaTeX 的 cryptic 错误转为可读提示

**违背初心？** 否。封装的是配置细节，暴露的是语义化 API；底层仍是标准 LaTeX + ffmpeg，无魔法。

---

## 附录：初心一致性检查

MaCode 的七条初心与本次全部修改的对照：

| 初心 | 含义 | 本次修改是否违背 | 说明 |
|------|------|----------------|------|
| **Bash-First** | 所有编排基于 Linux shell 脚本，Agent 通过 bash 探索、组合、修复 | ✅ 保持一致 | 新增的全部功能（硬件检测、渲染、校验）都是 `.sh` 或 `.py` 脚本；方案 C（Windows 原生）因违背此条被拒绝 |
| **引擎无关** | 场景定义与引擎实现解耦，`manifest.json` 是唯一切换点 | ✅ 保持一致 | ManimGL 作为新引擎，仍通过 `manifest.json` 的 `engine` 字段切换；`engine.conf` 自描述 |
| **管道透明** | 渲染、剪辑、压缩的每一步都是可见的文件转换 | ✅ 保持一致 | `.agent/tmp/{scene}/frames/` 物理保留帧序列；`.agent/log/` 保留完整日志；JSON 画像可 `cat`/`jq` |
| **状态可逆** | Agent 行为通过 Git 流控制实现原子化与可回滚 | ✅ 保持一致 | 未修改 Git 流控制逻辑；`agent-run.sh` 仍然包装所有任务 |
| **音频统一** | 所有音频处理由 `ffmpeg` 完成 | ✅ 保持一致 | `audio_builder.py` 底层仍是 ffmpeg；未引入 sox 或其他音频工具 |
| **Agent 可理解** | 文件系统环境透明，可被 `ls / cat / grep` 完全理解 | ✅ 保持一致 | 所有配置是文本（JSON/YAML/Markdown）；硬件画像是 JSON；SOURCEMAP 消费 JSON；无二进制黑箱 |
| **UNIX 哲学** | 文本流、小工具组合、单一职责 | ✅ 保持一致 | `detect-hardware.sh` 输出 JSON → `select-backend.sh` 读取 → `render.sh` 注入环境变量，纯管道组合；无守护进程、无数据库、无 Web 服务 |

### 唯一被主动拒绝的选项

**方案 C（Windows 原生渲染）**：
- 需要 Windows PowerShell 重写全部 20+ 个 bash 脚本
- 需要 Windows Python + 重新安装所有依赖
- WSL2 ext4 路径在 Windows 端不可用
- 结论：**违背 Bash-First 和 Agent 可理解原则**，被拒绝

---

*路线图版本：v0.4*  
*哲学：Make it work → Make it right → Make it fast*  
*当前阶段：Phase 7 完成，WSL2 D3D12 GPU 加速就绪 —— 2026-05-07*
