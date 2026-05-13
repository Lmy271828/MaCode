# Sprint 0 — 并行子智能体工单（S0-1〜S0-4）

仓库根：`/home/lenovo/pynoob/MaCode`  
工单来源：`docs/refactor-todo.md` § Sprint 0

四路并行：**无交叉依赖**。完成后由人类或主智能体做一次 `git add` / `git commit`（或分别提交）。

| ID | 角色 | 交付物 |
|----|------|--------|
| S0-1 | Git 基线冻结 | `refactor/2026Q2` 分支 + `pre-refactor-2026-05-13` 标签 |
| S0-2 | Smoke 基线快照 | `docs/baseline/snapshot-2026-05-13.json` |
| S0-3 | Escape hatch 清单 | `docs/baseline/escape-hatches.md` |
| S0-4 | 文档解锁 | `docs/progress.md` 顶行弃用提示 + `CHANGELOG.md` + `docs/roadmap.md` |

共性约定：

```bash
export PATH="/home/lenovo/pynoob/MaCode/bin:$PATH"
cd /home/lenovo/pynoob/MaCode
```

渲染基线时请使用 `--no-review`，避免卡住人工审核流程：

```bash
macode render "scenes/SCENE/" --no-review
```

## 子智能体 ID（最近一次并行启动，2026-05-13 续跑）

| 工单 | Cursor 子任务 Agent ID | 说明 |
|------|------------------------|------|
| S0-1 | `8d6cac4b-e5ce-4677-a328-9afd052bbf36` | `subagent_type: shell` — Git 分支与 tag（幂等） |
| S0-2 | `ab9bae78-f07f-4498-83d6-08a7b3fffe4f` | 全量 smoke + 覆盖写入 `snapshot-2026-05-13.json` |
| S0-3 | `e9782a1c-aff5-4c22-8f1e-a4ccd81817f3` | 再生 `escape-hatches.md` |
| S0-4 | `44e90da9-dc48-4175-85ca-4fdb9fd03e08` | `CHANGELOG.md`（刷新最近 14 条）/ `roadmap.md` / `progress.md` 幂等 prepend |

主会话已修复 **`engines/manim/scripts/render.sh`**：在 **keyframes 段之前**初始化 `PYTHON`（`set -u`），以便 S0-2 能通过 `macode render`。

## 收口检查清单

```bash
git tag -l 'pre-refactor-*'
git branch --list 'refactor/*'
ls docs/baseline/
test -f docs/baseline/escape-hatches.md && test -f CHANGELOG.md && test -f docs/roadmap.md && head -2 docs/progress.md
```
