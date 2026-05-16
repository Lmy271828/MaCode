# MaCode 文档索引

日常维护以仓库根目录 **`CHANGELOG.md`**、本文档目录下的 **`refactor-todo.md`**、**`PRD-draft.md`** 为准。

> **`progress.md`** 已归档至 `docs/archive/progress.md`；需要「当前事实」时优先 `CHANGELOG.md` 与 `refactor-todo.md`。

## 产品与路线

| 文档 | 说明 |
|------|------|
| [PRD-draft.md](./PRD-draft.md) | 产品需求草案（范围、原则、里程碑） |
| [roadmap.md](./roadmap.md) | 路线图占位，指向 refactor-todo / PRD |
| [refactor-todo.md](./refactor-todo.md) | 按 Sprint 的可执行工单与验收 |
| [reduction-plan-deletion-risk.md](./reduction-plan-deletion-risk.md) | 减法计划、替代方案、风险（R1–R9） |

## 架构与安全

| 文档 | 说明 |
|------|------|
| [architecture.md](./architecture.md) | 目录结构、安全深度、WSL2、仪表盘、人类介入、并发 |
| [security-architecture.md](./security-architecture.md) | 安全架构补充 |
| [task-state-schema.md](./task-state-schema.md) | `state.json` 等任务状态约定 |
| [SOURCEMAP_SPEC.md](./SOURCEMAP_SPEC.md) | SOURCEMAP 协议说明（与 `engines/*/sourcemap.json` 对齐） |

## 专项设计

| 文档 | 说明 |
|------|------|
| [shader-preview-design.md](./shader-preview-design.md) | Shader WebGL 预览（多段为历史规格；稳定 CLI 已退役至 `experimental/`） |
| [C-shader-pipeline-plan.md](./C-shader-pipeline-plan.md) | Layer 2 shader 管道与 ManimGL 侧关系 |
| [auto-fix-design.md](./auto-fix-design.md) | 画面自纠 / fix 流设计草案 |
| [narrative-integration-plan.md](./narrative-integration-plan.md) | 叙事模板与 MC 集成规划 |
| [host-agent-skill-plan.md](./host-agent-skill-plan.md) | Host Agent Skill 规划（与 PRD「单宿主」对齐时需留意文中旧 Multi-Agent 表述） |

## 基线与快照

| 路径 | 说明 |
|------|------|
| [baseline/escape-hatches.md](./baseline/escape-hatches.md) | `rg` 扫描输出的 escape hatch 基线（**静态快照**，部分行可能指向已删除文件，见文件头说明） |
| [baseline/SPRINT*-SUBAGENTS.md](./baseline/) | 各 Sprint 子任务记录 |

## 其它

| 文档 | 说明 |
|------|------|
| [adr-012-mc-engine-split.md](./adr-012-mc-engine-split.md) | ADR：MC 编排/执行拆分（**正文为 2026-05-10 讨论**；当前实现为统一 `render.mjs`，见文首补充） |
| [test-plan.md](./test-plan.md) | 测试阶段规划（愿望清单） |
