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
| `cat .macode/settings.json` | 拦截 | ✓ REJECTED |
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
