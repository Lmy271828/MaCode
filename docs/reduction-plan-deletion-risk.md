# 减法计划：删除清单、替代方案与风险评估

> **状态**：执行前评审用  
> **日期**：2026-05-13  
> **关联**：[PRD-draft.md](./PRD-draft.md)

本文档列出建议从 MaCode 中**删减或降级**的范畴，每一项包含：**删除/降级对象**、**替代方案**、**风险与缓解**。  
实际删改前需在仓库内跑通 `macode test`（或项目约定的 smoke/integration），并更新 README/AGENTS 中的入口说明。

---

## 总原则

- **先文档与入口收敛，再删代码**：避免「删了功能但文档仍引用」造成更高支持成本。  
- **按依赖顺序删**：先关掉默认路径上的隐式行为（如默认 review），再删 Multi-Agent 与守护进程。  
- **保留「一个能跑通的 hello world」**：任何减法不得使「新克隆 → 单场景出片」路径断裂。

---

## 清单总览

| ID | 项 | 建议动作 | 风险等级 |
|----|----|----------|----------|
| R1 | Multi-Agent 协调（claim / queue / …） | ~~删除~~ **Sprint 6 已按 PRD 落地**（`max_concurrent_scenes` 仍为本机并行） | （曾）高 |
| R2 | 渲染后默认 `review_needed` + exit 3 阻塞 | 默认关闭或独立子命令 | 中 |
| R3 | `composite` 与 `composite-unified` 双轨 | 合并为一种或明确弃用一种 | 高 |
| R4 | ZoneScene / NarrativeScene / Layout Compiler 三者并存 | 保留 1～2 个，其余 experimental | 高 |
| R5 | `pipeline/render-scene.py` 上帝脚本 | 拆分为子 CLI 或保留薄壳 + 文档 | 中 |
| R6 | `AGENTS.md` / README / Skill / progress 重复 | 合并信息架构，删 progress 中的设计混写 | 低 |
| R7 | `scenes/` 内 demo 与 fixture 混杂 | 迁移到 `tests/fixtures` 或 `examples/` | 中 |
| R8 | Motion Canvas 旁路复杂度（browser pool / guardian / 多脚本） | 保留最小路径，其余标 experimental | 中 |
| R9 | SOURCEMAP 多工具链（sync / lint / scan / validate） | 保留核心，合并或删减维护脚本 | 低～中 |

---

## R1 — Multi-Agent 协调子系统

**状态（2026-05-13）**：PRD 决定不做 Multi-Agent；Sprint 6 已从默认路径移除 claim、`MACODE_AGENT_ID`、`/api/queue`、exit 4/5；`cleanup-stale` 不再扫描 claim。**保留**：本机并行上限 `max_concurrent_scenes`、`bind()` 抢端口、flock（检查报告/Git）。

### 删除/降级对象（典型；多数已完成）

- `bin/checks/_utils.py` 中的 scene claim、`render-scene.py` 内 `claim_scene` / `atexit` 释放、`--no-claim`
- exit 码 4（claimed）、5（queued）及文档中的重试约定
- `bin/cleanup-stale.py` 中与 claim/PID 强相关的清理逻辑（若仅此用途）
- `project.yaml` 中 `max_concurrent_scenes` 与运行时排队语义
- Dashboard / API 中与 queue、多 Agent 占用的展示（若存在且仅服务该场景）

### 替代方案

- **单行串行**：同一项目内约定「一次只跑一个 render」；或由用户在 shell 层 `flock .agent/macode-render.lock pipeline/render.sh ...`。
- **若仍需并行**：保留 **文件锁** 作为唯一原语（flock），不引入 agent_id、不维护跨场景队列状态机。

### 风险

| 风险 | 可能性 | 影响 | 缓解 |
|------|--------|------|------|
| 多终端同时 render 踩踏同一 `.agent/tmp/{scene}` | 中 | 输出损坏或竞态 | 文档声明 + flock 示例；或对单 scene 目录加锁 |
| 贡献者依赖 exit 4/5 写自动化循环 | 低 | CI/脚本被破坏 | CHANGELOG 标注破坏性变更；提供 `macode render` 包装示例 |
| 删除后「并发渲染」变慢 | - | 需接受或可外包给 GNU parallel | 用进程外并行（不同 scene、不同 checkout） |

---

## R2 — 默认人机 Review（review_needed / exit 3）

### 删除/降级对象

- 成功渲染后默认 `touch review_needed`、`render` 在非 `--no-review` 下 exit 3 当文件已存在等行为（以当前代码为准逐项核对）
- 文档中「每次渲染必经人工」的叙事

### 替代方案

- **默认**：渲染成功即 exit 0，产物可用；质检用 `macode check`/`report` **显式**执行。
- **可选**：`macode render --review` 或环境变量启用「完成后进入待审状态」。

### 风险

| 风险 | 可能性 | 影响 | 缓解 |
|------|--------|------|------|
| 无人把关导致低质量合并 | 中 | 内容质量波动 | PRD 将责任放在可选 check + 人工流程 |
| 旧脚本依赖 exit 3 | 低 | 自动化误判 | 版本说明 + grep 仓库内 `exit 3`/`awaiting_review` 引用并更新 |

---

## R3 — Composite 双轨（`composite` vs `composite-unified`）

### 删除/降级对象

- manifest `type` 二选一其中之一：`composite` **或** `composite-unified` 对应的整条 pipeline（Python 编排、文档、示例场景）
- `macode composite ...` 中与已弃用类型绑定的子命令说明

### 替代方案

- **叙事连续、单 Scene**：统一用 composite-unified 思路（单进程顺序）**或**
- **工程并行、ffmpeg 拼接**：统一用分段渲染 + concat/xfade。

保留一种并在 PRD「开放问题」中写死选型理由。

### 风险

| 风险 | 可能性 | 影响 | 缓解 |
|------|--------|------|------|
| 现有用户场景依赖被删类型 | 中 | render 失败 | 迁移文档：manifest 字段映射表 + 一段迁移脚本或一次性 sed 说明 |
| 性能特征变化（并行 vs 单实例） | 高 | 渲染时间/内存 | 在 PRD 成功指标中区分「推荐路径」的适用规模 |

---

## R4 — Zone / Narrative / Layout Compiler 重叠

### 删除/降级对象（择一策略）

- **策略 A**：只保留 **手写 scene +（可选）MaCodeScene 基类**；Zone/Narrative/Compiler 全部标 `experimental/` 或移出主文档。
- **策略 B**：只保留 **Layout Compiler + 一种布局模板**；Zone/Narrative 降级为示例。
- **策略 C**：只保留 **Zone + Narrative**（仅 Manim 系），删除 Compiler。

### 替代方案

- 文档中仅保留一条「推荐抽象」；其余移入 `docs/archive/` 或删除代码路径上的自动检查（避免未继承某基类就跳过检查造成行为分裂）。

### 风险

| 风险 | 可能性 | 影响 | 缓解 |
|------|--------|------|------|
| 已有场景 `check-layout`/`check-narrative` 行为变化 | 中 | CI 失败 | 分阶段：先改默认不强制，再删代码 |
| 教育向用户喜爱 Zone 约束 | 低 | 社区反馈 | 以 plugin 或 `engines/manimgl` 扩展形式保留最小集 |

---

## R5 — `render-scene.py` 体量与职责

### 删除/降级对象

- 单文件内联：服务启动、缓存、api-gate、多层 check、编码、deliver、progress 等（不删功能的前提下拆文件）

### 替代方案

- **拆分为**：`validate_scene`、`run_engine`、`fuse_and_encode`、`deliver_artifact`（名称示例），由 `render.sh` 或极薄 orchestrator 顺序调用。
- **或**：保留单文件但对阶段设 **明确子函数模块**（同一包内 import），并把「阶段图」写进 README 一页图。

### 风险

| 风险 | 可能性 | 影响 | 缓解 |
|------|--------|------|------|
| 拆分引入重复解析 manifest | 低 | 性能微降 | 单次读 manifest 传入上下文或 tempfile |
| 子进程边界增多 | 中 | 调试变难 | 统一 `LOG_PREFIX` 与 stage id 写入同一 log |

---

## R6 — 文档与 Skill 重复

### 删除/降级对象

- `AGENTS.md` 中与 `README`「快速开始」逐字重复的大段
- `.agents/skills/macode-host-agent/SKILL.md` 与 `AGENTS` 完全重复的工作流（保留一处权威源）
- `docs/progress.md` 中已完成项与设计储备混在一起的长文（迁至 CHANGELOG / ADR）

### 替代方案

- **单一权威**：`README` = 人类 5 分钟上手；`AGENTS.md` = Agent 约束 + 链接到 Skill；Skill = 可复制的工作流片段。
- `progress.md` → `CHANGELOG.md`（按版本）+ `docs/design/`（仅进行中设计）。

### 风险

| 风险 | 可能性 | 影响 | 缓解 |
|------|--------|------|------|
| 外部链接锚点失效 | 中 | 404 或旧缓存 | 重定向小节或保留旧路径 stub 一段话 |

---

## R7 — `scenes/` 卫生（demo vs fixture）

### 删除/降级对象

- 明显为测试用途的 composite 片段目录、重复 base_demo 变种等（列出具体目录需一次 `rg`/清单评审）
- `scenes/` 根下非目录文件（如 `test_marker.txt`）

### 替代方案

- `examples/` 或 `tests/fixtures/scenes/`：`04_base_demo_*`、自纠正测试等迁入后改 smoke 路径引用

### 风险

| 风险 | 可能性 | 影响 | 缓解 |
|------|--------|------|------|
| smoke/integration 路径硬编码 | 高 | 测试全红 | 先全局替换路径再删旧目录 |
| 用户误用 examples 当模板 | 低 | 命名混淆 | README 标明「复制自 examples/xxx」 |

---

## R8 — Motion Canvas 工具链减法

### 删除/降级对象（可选幅度）

- **激进**：browser pool、server guardian、多条 dev server 路径中仅保留 `render-cli.mjs` 所需最小闭环
- **温和**：guardian/browser pool 标为 `--experimental`，默认关闭

### 替代方案

- 文档写明：MC 主推路径为 `render-cli.mjs + Playwright`，性能优化项可关。

### 风险

| 风险 | 可能性 | 影响 | 缓解 |
|------|--------|------|------|
| 多幕并发内存回升 | 中 | OOM | 文档建议降低并行度或减少 keep-server |
| WSL2 长时间驻留进程 | 低 | 资源泄漏体感 | guardian 删减后用文档提醒手动 `mc stop` |

---

## R9 — SOURCEMAP 工具链

### 删除/降级对象

- 合并 `sourcemap-lint`、`sourcemap-sync`、`sourcemap-scan-api`、`sourcemap-version-check` 中为同一维护动作重复的实现（非删协议本身）

### 替代方案

- `macode sourcemap validate` 单入口编排：lint → sync → validate paths → version-check（已实现部分可扩充）
- 或长期：Markdown 仅为人类读本，仓库内 **唯一真源为 JSON**，由 CI 生成 MD（方向性，改动大）

### 风险

| 风险 | 可能性 | 影响 | 缓解 |
|------|--------|------|------|
| 贡献者不知如何更新 whitelist | 中 | PR 被拒 | SKILL 增加「三步更新 SOURCEMAP」 |
| api-gate 与 MD 脱节 | 低 | 假阴性/假阳性 | CI 强制 sync |

---

## 建议执行顺序（依赖）

```text
1. R6 文档瘦身（无代码风险，先统一叙事）
2. R2 默认 review 行为（减少自动化与 Multi-Agent 假设）
3. R7 scenes 搬迁 + 测试路径更新
4. R1 Multi-Agent 减法（破坏性最大，需 CHANGELOG）
5. R3 / R4 产品与 PRD 选型绑定后执行
6. R5 / R8 / R9 工程化与维护性，可并行小步 PR
```

---

## 回滚与验证

| 验证项 | 命令/动作 |
|--------|-----------|
| 单元/集成/冒烟 | `macode test --all`（或项目约定子集） |
| 单场景 render | `pipeline/render.sh scenes/01_test/`（及 MC/ManimGL 各一例） |
| Composite（若保留） | 选 `scenes/04_composite_demo` 或等价 fixture |
| 文档链接 | 全文搜索已删子命令与 exit 码 |

---

## 附录：破坏性变更登记表（实施后填写）

| 日期 | 变更 ID | 摘要 | PR/Commit |
|------|---------|------|-----------|
| | | | |
