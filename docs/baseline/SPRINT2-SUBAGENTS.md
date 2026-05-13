# Sprint 2 — 子智能体工单（S2-1〜S2-3）

> **来源**：[`docs/refactor-todo.md` § Sprint 2](../refactor-todo.md)  
> **仓库根**：`/home/lenovo/pynoob/MaCode`

## 并行边界（重要）

| 工单 | 主要触及 |
|------|----------|
| **S2-1** | `bin/macode_state/`（新建）、`pipeline/render-scene.py`、`pipeline/composite-render.py`、`pipeline/composite-unified-render.py`、`bin/state-write.py`、`bin/progress-write.py`、`bin/macode-run` |
| **S2-2** | 同上 `macode_state` + **`docs/task-state-schema.md`**（新建）、`bin/dashboard-server.mjs`、`tests/unit/test_macode_state.py` |
| **S2-3** | **`pipeline/render-scene.py`**、`bin/copilot-feedback.py`、`README.md`、`tests/unit/test_copilot_feedback.py` |

**S2-1 与 S2-3 同改 `pipeline/render-scene.py`**，同迭代内**不得**分两路并行改该文件。

**推荐执行模型**：单次子任务 **顺序**完成 **S2-1 → S2-2 → S2-3**（代号 **S2-ALL**）。若Must 拆分：先合并 **S2-1+S2-2**，再开独立子任务做 **S2-3**，且第二段启动前必须 rebase / 同步第一段。

## 环境与验收（全体）

```bash
export PATH="/home/lenovo/pynoob/MaCode/bin:$PATH"
cd /home/lenovo/pynoob/MaCode
pytest tests/unit/test_macode_state.py tests/unit/test_copilot_feedback.py -q
rg -n 'def write_state|def write_progress' bin/ pipeline/   # 应仅剩 macode_state 或允许的薄封装说明
rg -n 'copilot-feedback' pipeline/render-scene.py            # S2-3 后应为 0 匹配
```

完整五场景渲染可选、耗时；CI 或人类在合并后触发。

## 子智能体 ID（启动后回填）

| 子任务 | 说明 | Cursor Agent ID |
|--------|------|-----------------|
| **S2-ALL** | S2-1 → S2-2 → S2-3 同一执行者顺序完成 | `40ef1d0e-aecc-43e8-8329-8bfec1ab95f3` |

## `macode-run` 与 orchestration state 的差异（实现提示）

- **Pipeline / composite**：`write_state(scene_name, …)` 写的是 `.agent/tmp/<scene>/state.json` 的轻量编排形态（现有 `version`/`taskId`/`status`/`exitCode`/时间戳）。
- **`macode-run`**：仍为 **MaCode Task State**（含 `cmd`、`pid`、`outputs`、合并 `task.json` 等）；S2-1 应至少将 **原子写 JSON** 与 **`--progress` 的 jsonl 追加** 委托给 `macode_state` 内共享 helper，避免再复制 `tmp + replace` 逻辑。
- **`state-write.py` / `progress-write.py`**：保持 CLI 契约不变，内部改为调用 `macode_state`。

## S2-3 `copilot-feedback` 解体约定

- 从 `render-scene.py` 删除 TTY + `subprocess.Popen(…copilot-feedback…)` 整段。
- `bin/copilot-feedback.py` 提供 **`watch <scene>`**（轮询或可选用 `inotify`）：监视 `.agent/tmp/<scene>/frames/`（或文档约定路径），与渲染进程解耦。
- 更新 `tests/unit/test_copilot_feedback.py`；`README.md` 增加「可选工具」小段。

---

*主会话启动子任务后会把上表 Agent ID 填回。*
