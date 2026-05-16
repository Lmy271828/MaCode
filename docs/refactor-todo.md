> **文档状态**：本文件部分引用组件可能已删除或重构（如 `cache.sh`、`security-run.sh` 等）。以 `AGENTS.md` §9 CLI 速查表和 `.agents/skills/` 为当前真源。发现引用过时组件？请直接修复。
>
> *(本文件作为历史任务工单池保留，不保证所有任务条目与当前代码一致。)*

# MaCode 重构 TODO 清单（按迭代周期）

> **状态**：执行用工单池  
> **日期**：2026-05-13  
> **关联文档**：[PRD-draft.md](./PRD-draft.md) · [reduction-plan-deletion-risk.md](./reduction-plan-deletion-risk.md)

本文件把"系统架构师批判"中的具体建议拆成**可独立合并、可回滚**的工单，按迭代周期（≈1 周/迭代）组织。每个工单包含：动机、影响文件、执行步骤、验收标准、回滚方式、依赖。

---

## 阅读说明

- **优先级**：`P0` = 阻塞后续 / 数据丢失风险 / 已知 bug；`P1` = 高 ROI 减法；`P2` = 长期价值。
- **风险**：🟢 低 / 🟡 中 / 🔴 高（不可逆 / 范围大 / 影响外部消费者）。
- **依赖**：`需先完成 #X` 表示前置工单。
- **可并行**：标记 ⇄ 的工单同迭代内可由不同执行者并行。
- **验收命令**：每个工单结束前必须执行的回归命令。

---

## Sprint 0 — 基线封冻（0.5 周）

**目标**：在动任何代码前先把"现状"钉死，建立可回滚基线与测试基线。

### S0-1 · 创建重构基线分支与标签 · P0 · 🟢
- **动作**：从 `master` 切 `refactor/2026Q2` 分支；打 `pre-refactor-2026-05-13` git tag。
- **验收**：`git tag -l pre-refactor-*` 显示；`git log refactor/2026Q2 -1` = master head。
- **回滚**：N/A。

### S0-2 · 建立 smoke 基线快照 · P0 · 🟢
- **动作**：在主要 scene 上跑全套 smoke，把输出 mp4 的 hash、frame count、时长记录到 `docs/baseline/snapshot-2026-05-13.json`：
  ```bash
  macode render scenes/01_test/
  macode render scenes/02_shader_mc/
  macode render scenes/04_base_demo/
  macode render scenes/04_composite_demo/
  macode render scenes/09_zone_test/
  ```
- **验收**：每个场景的 `final.mp4` 大小、ffprobe duration、`ls frames/ | wc -l` 写入快照文件并提交。
- **回滚**：N/A。

### S0-3 · 列举所有 escape hatch · P1 · 🟢
- **动作**：`rg -n -- '--no-claim|--no-review|--skip-checks|--fresh|--keep-server|fallback|guardian|stale|override|bypass' bin/ pipeline/ engines/` → 输出存到 `docs/baseline/escape-hatches.md`，作为后续删除工单的清单。
- **验收**：文件存在并提交。
- **回滚**：删除文件。

### S0-4 · 文档死锁解锁 · P1 · 🟢 ⇄
- **动作**：在 `docs/progress.md` 顶部追加一行 `> 本文件已弃用，请阅读 CHANGELOG.md 与 docs/roadmap.md`，**不删内容**。建立空的 `CHANGELOG.md`（从最近 14 个 commit 倒序填）和 `docs/roadmap.md` 占位。
- **验收**：`CHANGELOG.md` 存在；`docs/progress.md` 顶部有弃用提示。
- **回滚**：`git revert`。

---

## Sprint 1 — 廉价胜利：消除矛盾配置（1 周）

**目标**：删除"声明 vs 现实不一致"的配置/超时/默认值，**无功能变化、收敛认知噪音**。

### S1-1 · R-A 删除双重超时 · P0 · 🟡
- **动机**：`engines/manim/scripts/render.sh` 用 GNU `timeout`，`bin/macode-run` 又用 `child.wait(timeout=)`，两者叠加产生不可预测 exit code（124 / -9 / 1）。
- **影响文件**：
  - `engines/manim/scripts/render.sh`（删除 `MAX_TIME` + `timeout --foreground`）
  - `engines/manimgl/scripts/render.sh`（同上）
  - `bin/macode-run`（保留为唯一超时源）
- **步骤**：
  1. 在 `engines/manim/scripts/render.sh` 删除 `MAX_TIME` 读取段（line ~148-162）与 `timeout --foreground "$MAX_TIME"` 包装（line ~166）。
  2. 在文件顶部 docstring 加注：`timeout enforced by upstream bin/macode-run; this script must NOT wrap with GNU timeout`.
  3. `manimgl/scripts/render.sh` 同样处理。
  4. 在 `bin/macode-run` 读 `project.yaml` 的 `agent.resource_limits.max_render_time_sec` 作为默认 `--timeout`（之前是硬编码 600）。
- **验收**：
  - `S0-2` 的 5 个 scene 全部成功，timing 偏差 ≤5%。
  - 故意写一个 `while True: pass` 场景，确认 `macode-run` 在配置秒数后送 SIGTERM。
- **回滚**：`git revert`；恢复 `timeout` 行即可。
- **依赖**：无。

### S1-2 · 默认引擎统一化 · P0 · 🟢
- **动机**：`project.yaml`=manimgl、`README.md`=manim、`bin/macode` fallback=manim、`AGENTS.md`=manimgl，4 处不一致。
- **影响文件**：`project.yaml`、`README.md`、`AGENTS.md`、`bin/macode`（line ~25 `DEFAULT_ENGINE="manim"`）。
- **步骤**：
  1. 团队/作者在 PRD 中做一次性选型决策（记录在 `docs/PRD-draft.md` §8 「开放问题」）。
  2. 把决定值写进 `project.yaml`。
  3. `bin/macode` 改为：若 `project.yaml` 不存在才 fallback 到 manim；否则不再硬编码 default。
  4. README/AGENTS 改为 `参见 project.yaml.defaults.engine` 一句话引用，不再重复值。
- **验收**：`rg -n 'default.*engine|engine.*default' README.md AGENTS.md` 只剩对 `project.yaml` 的引用。
- **回滚**：`git revert`。
- **依赖**：无。

### S1-3 · `engine.conf` 删除装饰性字段 · P1 · 🟢 ⇄
- **动机**：`cli_signature` / `output_pattern` 注释自承"reserved for future"，但实际 `render.sh` 硬编码 CLI args；伪契约。
- **影响文件**：`engines/manim/engine.conf`、`engines/manimgl/engine.conf`、`engines/motion_canvas/engine.conf`、`bin/inspect-conf.py`。
- **步骤**：
  1. 删除三处 `engine.conf` 中的 `cli_signature` 和 `output_pattern` 块。
  2. `bin/inspect-conf.py` 同步删掉这两段解析。
  3. 保留：`name`、`mode`、`version_cmd`、`compatibility`、`scene_extensions`、`render_script`、`pre_render_script`、`service_script`、`service_port_min/max`、`inspect_script`、`validate_script`、`sourcemap`。
- **验收**：`macode engine` 输出正常；`pipeline/render-scene.py` 渲染所有 baseline 场景成功。
- **回滚**：`git revert`。
- **依赖**：无。

### S1-4 · YAML 解析单一化 · P1 · 🟢 ⇄
- **动机**：`bin/inspect-conf.py` 有 `parse_with_yq` + `parse_with_grep` 两套；`bin/checks/_utils.py` 已用 PyYAML；冗余且不一致。
- **影响文件**：`bin/inspect-conf.py`、`requirements.txt`（确认 `pyyaml` 已声明）。
- **步骤**：
  1. 删除 `parse_with_grep`、`parse_with_yq`。
  2. 改为：
     ```python
     import yaml
     with open(path) as f:
         data = yaml.safe_load(f) or {}
     return {k: data[k] for k in ('mode', 'scene_extensions', ...) if k in data}
     ```
  3. `setup.sh` 中保留 `yq` 安装项以兼容 bash 调用（`bin/macode`、`render.sh`），但 Python 路径只用 `yaml.safe_load`。
- **验收**：单测 `tests/unit/test_inspect_conf.py` 全过；删除/隔离 yq 后仍能解析。
- **回滚**：`git revert`。
- **依赖**：无。

### S1-5 · 日志轮转 · P1 · 🟢 ⇄
- **动机**：`.agent/log/` 已有 735 个 `.log` 文件，5.2MB，无自动清理。
- **影响文件**：`bin/cleanup-stale.py` 或新建 `bin/log-rotate.py`。
- **步骤**：
  1. 在 `bin/cleanup-stale.py` 加 `--logs` 子动作：保留最近 30 天或最近 200 个文件，多余的删除。
  2. `setup.sh` 提示用户在 cron / Task Scheduler 里加 `0 3 * * * cd $MACODE && bin/cleanup-stale.py --logs`。
- **验收**：`.agent/log/` 文件数被压到上限；既往 baseline 场景仍能渲染。
- **回滚**：`git revert`。
- **依赖**：无。

---

## Sprint 2 — 统一 IO 边界（1 周）

**目标**：消除 5 套 state/progress 写入实现，建立**唯一**状态 IO API。

### S2-1 · R-B 建立 `macode_state` 模块 · P0 · 🟡
- **动机**：`pipeline/{render-scene,composite-render,composite-unified-render}.py` 各内联一份 `write_progress` / `write_state`；`bin/state-write.py` 又是独立 CLI；`bin/macode-run` 内部再有一份。任何 schema 演进都要改 5 处。
- **影响文件**：
  - **新增**：`bin/macode_state/__init__.py`（Python 包，可 `from macode_state import write_state`）
  - **改写**：3 个 pipeline 脚本、`bin/state-write.py`（变成薄 CLI wrapper）、`bin/progress-write.py`（同）、`bin/macode-run`
- **步骤**：
  1. 新建 `bin/macode_state/__init__.py`，提供：
     ```python
     def write_state(scene_name: str, status: str, *,
                     exit_code: int = 0, outputs: dict | None = None,
                     error: str | None = None,
                     started_at: str | None = None,
                     ended_at: str | None = None) -> None: ...

     def write_progress(scene_name: str, phase: str, status: str,
                        *, message: str = "", extra: dict | None = None) -> None: ...

     def read_state(scene_name: str) -> dict | None: ...
     ```
     内部包含：原子写、ISO 时间、`outputs` 合并、目录 mkdir、JSON schema 版本号。
  2. 3 个 pipeline 脚本：删除内联 `def write_state` / `def write_progress`，改为 `from macode_state import write_state, write_progress`。
  3. `bin/state-write.py` / `bin/progress-write.py` 改写为 ~30 行 argparse → 调用 `macode_state.write_*`。bash 调用方不需改。
  4. `bin/macode-run` 同样改为 import `macode_state`。
- **验收**：
  - `rg -n 'def write_state|def write_progress' bin/ pipeline/` 只剩 `bin/macode_state/__init__.py` 一处。
  - baseline 5 个 scene 全部成功；`.agent/tmp/*/state.json` 的字段集合与 baseline diff 为空。
  - 新增 `tests/unit/test_macode_state.py`：测试原子写、outputs 合并、错误路径不破坏既有 state。
- **回滚**：`git revert`；如果只破坏了 composite 链路，可临时把 import 改回内联函数。
- **依赖**：无。

### S2-2 · State schema 版本化 · P1 · 🟡
- **动机**：当前 `state.json` 写 `version: "1.0"` 但无校验；不同 writer 字段差异未被检测。
- **影响文件**：`bin/macode_state/__init__.py`、`docs/task-state-schema.md`、`bin/dashboard-server.mjs`（读端）。
- **步骤**：
  1. 在 `macode_state` 引入一个 dataclass 或 TypedDict（`TaskState`），所有字段类型固定。
  2. 写入前做 `assert isinstance(...)`，schema 变更必走 `version: "1.1"`、`"1.2"` ... 。
  3. dashboard 读端做 `if state.get("version") not in {"1.0", "1.1"}: warn`。
- **验收**：跑一遍场景，dashboard 不报 warn；`tests/unit/test_macode_state.py` 加 schema validation case。
- **回滚**：`git revert`。
- **依赖**：S2-1。

### S2-3 · `copilot-feedback.py` 移出主路径 · P1 · 🟢 ⇄
- **动机**：TTY-only 路径侵入"Host-Agent-First"的 `render-scene.py`，与产品定位互斥。
- **影响文件**：`pipeline/render-scene.py`（line ~464-488 的 `if engine_mode == "batch" and sys.stdin.isatty()` 分支）、`bin/copilot-feedback.py`。
- **步骤**：
  1. 从 `render-scene.py` 删除 `copilot_proc = subprocess.Popen([...copilot-feedback.py...])` 整段。
  2. 改写 `bin/copilot-feedback.py` 为独立工具：`copilot-feedback.py watch <scene>`，通过 `inotify`（或简单轮询）跟随 `.agent/tmp/{scene}/frames/`，与 render 完全解耦。
  3. README 增加"可选"段落说明启动方式。
- **验收**：`render-scene.py` 中不再出现 `copilot-feedback`；baseline 5 个 scene 渲染时间无变化；手工启动 `copilot-feedback.py watch` 仍工作。
- **回滚**：`git revert`。
- **依赖**：无。

---

## Sprint 3 — Motion Canvas 子系统瘦身（1 周）

**目标**：把 7 个 `.mjs` + 1809 行 Motion Canvas 工具链合并为 2 个文件 + ~500 行。

### S3-1 · R-C 合并 serve / stop / playwright-render · P0 · 🟡

> **落地（2026-05）**：统一入口已交付为 `engines/motion_canvas/scripts/render.mjs`；下表「删除/合并」为工单原文留档。行数 ≤800 等目标见 `docs/baseline/SPRINT3-SUBAGENTS.md`（内联模板可能抬高 `wc -l`）。

- **动机**：每次渲染需要协调 3 个 mjs 与 1 份 state.json；启动顺序 race condition 多次出现在 progress.md。
- **影响文件**：
  - **删除**：`engines/motion_canvas/scripts/serve.mjs`、`stop.mjs`、`browser-pool.mjs`、`server-guardian.mjs`
  - **保留并合并**：`engines/motion_canvas/scripts/playwright-render.mjs` → 改名 `render.mjs`，吸收 serve/stop
  - `pipeline/render-scene.py` 中 service 启动/停止逻辑同步简化
- **步骤**：
  1. 新写 `engines/motion_canvas/scripts/render.mjs`：
     - 启动 Vite dev server（端口由 Vite 自己选，从 stdout 解析）
     - 等待 ready
     - 启动 Playwright，抓帧到 `<output_dir>/frame_%04d.png`
     - 关闭 Playwright + Vite（监听 SIGTERM 转发给整个进程组：`process.kill(-pid, 'SIGTERM')`）
     - 写 `state.json`、`task.json`（沿用现有 schema）
  2. `pipeline/render-scene.py` 中 `service_script` / `find_free_port` 等逻辑全部走 `render.mjs` 一个调用；删除 `service_url` 中间变量。
  3. `macode mc serve/stop` 子命令：保留为薄 wrapper，调 `render.mjs --serve-only` 与发送 SIGTERM。
  4. 删除 `engines/motion_canvas/engine.conf` 中 `service_script` / `service_port_min/max` 字段。
- **验收**：
  - `scenes/02_shader_mc/`、`scenes/01_test_mc/` 渲染成功，帧像素 hash 与 baseline 一致（容差：图像近似 diff <1%）。
  - `engines/motion_canvas/scripts/` 文件数从 10 降到 ≤4（`render.mjs`、`shader-prepare.mjs`、`inspect.sh`、`validate_sourcemap.sh`）。
  - `wc -l engines/motion_canvas/scripts/*.{mjs,sh}` 总行数 ≤ 800。
- **回滚**：`git revert`；保留旧 mjs 至少 1 周以便对比。
- **依赖**：S1-3（删除 `engine.conf` 装饰字段后字段集稳定）。

### S3-2 · `snapshot.mjs` 评估去留 · P2 · 🟢 · ✅ 已完成（2026-05-13）
- **动机**：progress.md 曾标「待确认是否仍被使用」。
- **步骤**：
  1. `rg -n 'snapshot\.mjs'`
  2. 删除 `engines/motion_canvas/scripts/snapshot.mjs`；`dev.sh` 改为直接 `node …/render.mjs --snapshot …`。
- **验收**：`macode dev scenes/02_shader_mc --snapshot 1.5`；`pytest tests/unit` 通过。
- **回滚**：`git revert`。
- **依赖**：S3-1。

---

## Sprint 4 — SOURCEMAP 数据模型治理（1 周）

**目标**：消除"Markdown 为源 + JSON 缓存 + 双解析器 + 5 个工具"的局面；以 JSON 为唯一源，Markdown 是生成产物。

### S4-1 · R-D-1 JSON 提升为唯一源 · P0 · 🔴
- **动机**：`api-gate.py` 有 Markdown fallback，安全工具违反 fail-closed 原则；4 个维护工具均围绕 Markdown→JSON 同步。
- **影响文件**：
  - **新增**：`engines/manim/sourcemap.json`、`engines/manimgl/sourcemap.json`、`engines/motion_canvas/sourcemap.json`
  - **改写**：`bin/api-gate.py`（删除 Markdown fallback）
  - **重构**：`bin/sourcemap-sync.py` → 反向：JSON → Markdown
  - **删除**：`bin/sourcemap-lint.py`（JSON 用 jsonschema 校验，无需手写 lint）
- **步骤**：
  1. 用当前 `bin/sourcemap-sync.py` 跑一次正向同步，把生成的 `.agent/context/{engine}_sourcemap.json` 复制为 `engines/{engine}/sourcemap.json`（提交到 git）。
  2. 写 `engines/sourcemap.schema.json`（JSON Schema）。
  3. `bin/api-gate.py`：只读 `engines/{engine}/sourcemap.json`；找不到就 exit 2（fail-closed）。**删除整个 Markdown fallback 段（line ~63-93）**。
  4. `bin/sourcemap-sync.py` 反向化：`sourcemap.json` → `engines/{engine}/SOURCEMAP.md`（人类可读视图）。CI 强制 `sourcemap.md` 与最新 `sync` 输出一致。
  5. 删除 `bin/sourcemap-lint.py`。
- **验收**：
  - `bin/api-gate.py scenes/01_test/scene.py engines/manim/sourcemap.json` 工作；删除 Markdown 文件后仍工作。
  - `tests/unit/test_api_gate.py` 全过；新增"无 JSON 直接 exit 2"测试。
  - `engines/*/SOURCEMAP.md` 与 `bin/sourcemap-sync.py --check` 输出一致。
- **回滚**：`git revert` 较复杂，**建议保留 Markdown 文件不删，仅把 api-gate 切到 JSON only**；先做 §S4-1 的步骤 3，确认无问题再做步骤 4-5。
- **依赖**：无。**注意：这是迭代里风险最高的一步**，建议放在单独 PR，并联系所有 Agent 客户端通知 schema 锁定。

### S4-2 · R-D-2 合并 sourcemap CLI · P1 · 🟢
- **动机**：4 个独立 CLI（sync/scan-api/version-check/validate）做的事可整合。
- **影响文件**：`bin/macode`（增加 sourcemap subcommand）、`bin/sourcemap-*.py`。
- **步骤**：
  1. `bin/macode sourcemap <verb>` 提供：`generate-md` / `scan-api` / `version-check` / `validate`。
  2. 旧脚本变成入口薄封装（保留兼容 1-2 个版本），最终在 CHANGELOG 中宣布弃用。
- **验收**：旧 CLI 仍可调用；新 verb 与旧 CLI 输出一致。
- **回滚**：`git revert`。
- **依赖**：S4-1。

### S4-3 · 删除 api-gate 的"假阴性"风险点 · P1 · 🟡
- **动机**：BLACKLIST 按引擎写，但 `pipeline/render-scene.py` 调 api-gate 时传 `engines/{engine}/SOURCEMAP.md`。如果 manifest `engine` 字段写错，黑名单不匹配 → 静默放行。
- **影响文件**：`bin/api-gate.py`、`pipeline/render-scene.py`。
- **步骤**：
  1. `api-gate.py` 接受 `--engine` 显式参数，与 sourcemap 路径里推断的 engine 名做一致性校验，**不一致 exit 2**。
  2. `render-scene.py` 调 api-gate 时**显式**传 `--engine $ENGINE`。
- **验收**：把 manifest `engine` 改成不存在的值，`render-scene.py` 报"engine.conf not found"而非走到 api-gate；把 engine 名拼错（`manm`），api-gate exit 2 拒绝。
- **回滚**：`git revert`。
- **依赖**：S4-1。

---

## Sprint 5 — 编排/适配层重构（1.5 周）

**目标**：把 `render-scene.py` 拆分为可单测的子模块；把双引擎重复的 ZoneScene 几何/验证逻辑提到共享层。

### S5-1 · R-E ZoneScene 几何与验证去重 · P0 · 🟡
- **动机**：`engines/manim/src/components/zoned_scene.py` 与 `engines/manimgl/src/components/zoned_scene.py` 80% 重复（`diff | wc -l = 84`）；几何/验证已经在 `utils/layout_geometry.py` 与 `utils/layout_validator.py`，但两个引擎各放一份。
- **影响文件**：
  - **新增**：`bin/macode_layout/__init__.py`（或 `engines/_shared/layout/`）—— 引擎无关
  - **改写**：两个 `zoned_scene.py` 各缩到 ~40 行 glue
  - **同理处理**：`narrative_scene.py`（diff 20 行）
- **步骤**：
  1. 把 `utils/layout_geometry.py` 与 `utils/layout_validator.py` 合并提到 `bin/macode_layout/` 或 `engines/_shared/layout/`（Python 包），只**一份**。
  2. 给两个引擎的 `utils/` 留一行 `from macode_layout import *` 兼容 import 路径（避免动场景源码）。
  3. ZoneScene 拆为 `ZoneLayoutMixin`（纯逻辑，引擎无关）+ 引擎特定的 `class ZoneScene(Scene, ZoneLayoutMixin)`。
  4. Narrative 同样处理。
- **验收**：
  - `scenes/09_zone_test/`、`scenes/10_narrative_test/` 渲染成功；像素 hash 与 baseline 一致。
  - `wc -l engines/{manim,manimgl}/src/components/*.py` 总和减少 ≥40%。
  - 新增 `tests/unit/test_zoned_scene_shared.py`、`test_narrative_scene_shared.py`。
- **回滚**：`git revert`。
- **依赖**：S0-2 baseline 已建立。

### S5-2 · `render-scene.py` 拆分为子模块 · P0 · 🔴
- **动机**：627 行做 20 件事；4 个 `--no-*` flag 表示有 4 个子职责未分离；难以单测。
- **影响文件**：
  - **新增**：`pipeline/_render/__init__.py`、`_render/validate.py`、`_render/engine.py`、`_render/encode.py`、`_render/lifecycle.py`
  - **改写**：`pipeline/render-scene.py` 缩为 ~80 行编排
  - ~~**改写**：`pipeline/composite-render.py` 直接 `from _render.engine import run` 而非 shell out~~（P0-2 已删除）
- **步骤**：
  1. `_render/lifecycle.py`：claim/release、review 标记、override 处理、进度写入。提供 `with lifecycle(scene, agent_id):` 上下文管理器。
  2. `_render/validate.py`：manifest 校验、api-gate、static checks（layout/narrative/density）。返回 `ValidationResult`。
  3. `_render/engine.py`：engine.conf 解析、pre-render shader、service 启动/停止、引擎调用。返回 `EngineRunResult`（含 frames_dir / frame_count / log_path）。
  4. `_render/encode.py`：cache check / concat / cache populate / deliver / fuse 检查。
  5. `render-scene.py` 顶层只剩：
     ```python
     with lifecycle(scene, args) as ctx:
         vresult = validate(scene, skip=args.skip_checks)
         eresult = engine.run(scene, ctx, vresult)
         encode(scene, ctx, eresult)
         ctx.mark_review_if_needed()
     ```
  6. ~~`composite-render.py` 中每个 segment：`from _render.engine import run; engine.run(segment, ctx_without_claim, ...)` → `--no-claim` 这个 escape hatch 消失。~~（P0-2 已删除）
- **验收**：
  - `wc -l pipeline/render-scene.py` ≤ 120。
  - `--no-claim` 从 CLI 中删除（composite 内部不再需要它）。
  - 5 个 baseline scene + 2 个 composite scene 全部成功；时长偏差 ≤5%。
  - 新增 `tests/unit/test_render_validate.py`、`test_render_engine.py`、`test_render_encode.py`、`test_render_lifecycle.py` 至少各 3 个测试用例。
- **回滚**：~~保留 `pipeline/render-scene-legacy.py` 1-2 个版本~~ `render_scene_legacy.py` 已删除（P0-1）；`render-scene.py` 纯为 orchestrator 薄入口。
- **依赖**：S2-1（macode_state 模块已建立）。

### S5-3 · Multi-Agent claim 模块定位修正 · P1 · 🟢 ⇄
- **动机**：`claim_scene` / `release_scene_claim` 写在 `bin/checks/_utils.py`，但被 `render-scene.py` 与 composite 路径调用——**不属于 checks**。
- **影响文件**：`bin/checks/_utils.py`、`bin/macode_concurrency/__init__.py`（新建）、所有 import 处。
- **步骤**：
  1. 把 claim/release/`file_lock`/`is_scene_claimed` 等搬到 `bin/macode_concurrency/`。
  2. `bin/checks/_utils.py` 保留 check 专用辅助函数。
  3. 所有 import 改路径。
- **验收**：`tests/integration/test_concurrent_claim.py` 全过。
- **回滚**：`git revert`。
- **依赖**：S5-2（同时改 render-scene.py 时一并迁移）。

---

## Sprint 6 — Cache 升级与可选删减（1 周）

### S6-1 · L2 帧级 cache（项目核心差异化） · P1 · 🟡
- **动机**：当前 cache 整目录粒度，0.1 秒的 `self.wait` 修改也会 invalidate 整段 mp4。Manim 渲染是 per-frame 线性的，**frame-level cache 是这套技术栈应该提供的差异化能力**。
- **影响文件**：`bin/cache-key.py`、`bin/cache-store.py`、`bin/cache-restore.py`、`pipeline/cache.sh`、新增 `bin/cache-frames.py`。
- **步骤**：
  1. 在 `cache-key.py` 之外增加 `cache-frame-key.py`：输入 (scene_hash, frame_idx, fps, resolution) → 帧级 hash。
  2. 引擎完成渲染后，新建一步：`cache-frames.py populate <frames_dir>` 把每个 PNG 存到 `.agent/cache/frames/<hash>.png`。
  3. 下次相同 hash → `cache-frames.py restore <hash> > frame_NNNN.png`。
  4. 命中策略：对每帧并行检查 cache；全部命中则跳过 engine；部分命中则只渲染缺失帧。**这一步需要 engine 支持范围渲染**，第一版可只在"全部命中"时跳过。
- **验收**：
  - 同一场景两次连续 `macode render` 第二次 cache hit，省去 engine 调用。
  - 改动一个 `self.wait(1.5)` 为 `self.wait(1.6)`：当前实现下场景重渲；frame-level 实现后只缺失 ~3 帧重渲（视引擎能力）。
- **回滚**：`git revert`。
- **依赖**：S5-2 拆分完成后 `_render.encode` 是干净的注入点。

### S6-2 · 删除 Multi-Agent 协调子系统（PRD 不做 Multi-Agent） · P2 · 🟢
- **动机**：见 [`reduction-plan-deletion-risk.md` R1](./reduction-plan-deletion-risk.md#r1--multi-agent-协调子系统)。PRD 已定不做 Multi-Agent。
- **已完成**：移除 scene claim / exit 4–5 / dashboard `queue` API；`macode_concurrency` 仅保留 `file_lock` + `write_json_atomic`；`cleanup-stale.py` 去掉 claim TTL；`macode-run` 不再写 `agentId`；文档与 skill 同步。
- **验收**：`rg` 无 `claim_scene`、`MACODE_SKIP_SCENE_CLAIM`、`/api/queue`；`pytest` 通过。

### S6-3 · 删除 Composite 双轨之一 · P2 · 🔴
- **动机**：见 reduction plan R3。
- **步骤**：等待 PRD 决策。
- **依赖**：PRD 决策。

---

## Sprint 7 — 文档与体验收敛（0.5 周）

### S7-1 · README 砍到 100 行内 · P1 · 🟢 · 部分完成
- **动作**：保留①一句话定义；②30 秒 hello world；③主推工作流的 5 个命令；④链接到 PRD / AGENTS / CHANGELOG。其余移走。
- **验收**：`wc -l README.md` ≤ 100。
- **现状（2026-05-13 复测）**：**426 行**；未达 ≤100，后续 Sprint 单独压缩。
- **回滚**：`git revert`。
- **依赖**：S1-2 默认引擎已唯一化。

### S7-2 · AGENTS.md 砍到 500 行内 · P1 · 🟢 · 部分完成
- **动作**：把 §3.1 目录结构 / §5.3-5.6 安全模型深度 / §6.6 WSL2 / §10 仪表盘 / §11 人类介入 / §12 并发模型 抽到 `docs/architecture.md`，AGENTS.md 留概览 + 链接。
- **验收**：`wc -l AGENTS.md` ≤ 500（Sprint 7 阶段验收阈值，长期目标 ≤ 300）。
- **现状（2026-05-13 复测）**：**614 行**（已抽架构文，仍超阈值）；**勿标「已完成」直至 ≤500**。
- **回滚**：`git revert`。
- **依赖**：S0-4 progress.md 已弃用。

### S7-3 · Skill 与 AGENTS 去重 · P2 · 🟢 · 待 follow-up
- **动作**：`.agents/skills/macode-host-agent/SKILL.md` 与 `AGENTS.md` 工作流段落取一个权威源；另一处只链接。
- **现状**：SKILL.md 169 行；AGENTS.md 仍偏长（见 S7-2）；下一 Sprint 单独做。
- **验收**：`diff` 主要工作流段，重复内容 < 10 行。
- **依赖**：S7-2（达标后）。

### S7-4 · 配置文件统一生成 · P2 · 🟢
- **动作**：写一个 `bin/agent-config-render.py`：从 `docs/agent-config-source.md`（或 `project.yaml.agent` 段）渲染出 `.cursorrules` / `.windsurf/rules.md` / `.aider.conf.yml` / `.claude/settings.local.json`。
- **验收**：4 份文件由脚本生成；CI 加 `--check` 防止手动漂移。
- **回滚**：`git revert`。
- **依赖**：S0-4 文档结构稳定。

---

## Sprint 8（可选 / 长期） — scenes/ 卫生与示例治理

### S8-1 · `scenes/` 与 `tests/fixtures/` 分离 · P1 · 🟡 · ✅ 已完成
- **动作**：见 reduction plan R7。
- **已落地**：
  1. ✅ `tests/fixtures/scenes/` 创建并写入 README（命名规范）
  2. ✅ `test_self_correction/`、`test_self_correction_mc/`、`test_layout_compiler/` 已迁入
  3. ✅ `tests/unit/test_macode_hash.py` 路径更新；smoke 测试用的是 `04_composite_demo`（demo 非 fixture），无需改
  4. 🟡 `scenes/test_marker.txt`（render-all 的 sentinel）保留不动；demo 类场景仍在 `scenes/`（设计上保留作"示范作品"）
- **验收**：`pytest tests/unit/test_macode_hash.py -v` 全过；`ls scenes/ | grep ^test_` 排除 `test_marker.txt`（sentinel 文件）后为空；或无 `test_*` 子目录
- **回滚**：`git revert`
- **依赖**：S0-2 baseline。

### S8-2 · `scenes/` 命名规范固化 · P2 · 🟢 · ✅ 已完成（约定层）
- **动作**：在 README/AGENTS 写明命名规则（如 `NN_topic_engine?`）；删除 `04_*` 系列里命名不规则的目录。
- **依赖**：S8-1。

---

## 全局甘特图（建议节奏）

```text
W1     [S0] 基线封冻 ━━┓
W1-W2  [S1] 廉价胜利 ━━╋━━ (S1-1..S1-5 并行)
W3     [S2] IO 边界 ━━━┛━━━━ (S2-1 → S2-2 → S2-3)
W4     [S3] MC 瘦身 ━━━━━━━━━━ (依赖 S1-3)
W5     [S4] SOURCEMAP ━━━━━━━━━━━━━ (S4-1 风险高，单 PR)
W6-W7  [S5] 拆分编排 ━━━━━━━━━━━━━━━━━ (依赖 S2-1)
W8     [S6] Cache 升级 ━━━━━━━━━━━━━━━━━━━
W8     [S7] 文档收敛 ━━━━━━━━━━━━━━━━━━━━━ (与 S6 并行)
W9+    [S8] 长期清理（可选）
```

---

## 风险预案（按 Sprint）

| Sprint | 最大风险 | 缓解 |
|--------|----------|------|
| S0 | 基线测试覆盖不足 | 至少 5 个不同引擎/类型场景纳入 baseline |
| S1 | 默认引擎切换破坏既有用户场景 | 在 CHANGELOG 显著位置注明，提供一行 sed 迁移命令 |
| S2 | macode_state 模块 import 路径污染 | 用绝对包名 `macode_state`，**不**用相对 import |
| S3 | Motion Canvas 合并后丢失"复用 dev server"性能 | 保留 `--keep-server` 行为，但实现简化 |
| S4 | SOURCEMAP JSON 化破坏 Agent 兼容性 | 单 PR + 公告 + Markdown 仍生成（只是变成"视图"） |
| S5 | render-scene 拆分引入回归 | ~~`MACODE_USE_LEGACY_RENDER=1` 至少保留 2 周~~ 已删除（P0-1） |
| S6 | Frame cache 命中策略错误导致输出"看似一样实则差一帧" | 加 perceptual hash 比对的可选 verify 模式 |
| S7 | 文档信息丢失 | 删除前先归档到 `docs/archive/` |

---

## 验收命令模板（每个工单结束前必跑）

```bash
# 1. 静态检查
macode test --lint

# 2. 单元测试
macode test --unit

# 3. 集成与冒烟
macode test --integration
macode test --smoke

# 4. 基线场景
for s in 01_test 02_shader_mc 04_base_demo 04_composite_demo 09_zone_test; do
    macode render "scenes/$s" --no-review
done

# 5. 与 baseline snapshot 对比
python3 docs/baseline/compare.py docs/baseline/snapshot-2026-05-13.json
```

---

## 完成定义（Definition of Done）

每个工单关闭前必须满足：

1. ✅ 验收命令全部通过（或在工单备注说明已知偏差）
2. ✅ 涉及行为变化的，CHANGELOG.md 有条目
3. ✅ 涉及配置/CLI 变化的，README 或 AGENTS 有同步
4. ✅ 涉及 schema 变化的，`docs/task-state-schema.md` 或 `engines/sourcemap.schema.json` 有更新
5. ✅ 单 PR 不跨 Sprint（避免回滚牵连）
6. ✅ Reviewer（即使是自己）能在 30 分钟内看完全部 diff

---

*本 TODO 清单为活文档。每次 Sprint 结束在 `CHANGELOG.md` 留 1-2 行总结，并把已完成的工单从此处标记 `[x]`。*
