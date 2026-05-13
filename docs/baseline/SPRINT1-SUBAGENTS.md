# Sprint 1 — 子智能体工单（S1-1〜S1-5）

> **来源**：[`docs/refactor-todo.md` § Sprint 1](../refactor-todo.md)  
> **仓库根**：`/home/lenovo/pynoob/MaCode`

## 并行分组（避免同文件冲突）

| 子任务 ID | 覆盖工单 | 独占关键路径 | 与其它任务冲突 |
|-----------|----------|--------------|----------------|
| **S1-A** | S1-1 | `engines/manim/scripts/render.sh`、`engines/manimgl/scripts/render.sh`（若有 `timeout`）、`bin/macode-run` | 否 |
| **S1-B** | S1-2 | `docs/PRD-draft.md` §8、`project.yaml`、`README.md`、`AGENTS.md`、`bin/macode` | 否 |
| **S1-C** | **S1-3 + S1-4** | `engines/*/engine.conf`、`bin/inspect-conf.py`、`tests/unit/test_inspect_conf.py`、`requirements.txt`（确认 PyYAML） | **必须单一路径**（inspect-conf 仅此 agent 改） |
| **S1-D** | S1-5 | `bin/cleanup-stale.py`、`bin/setup.sh`（或 `setup-dev.sh` 末尾提示） | 否 |

**Manimgl `render.sh`**：当前实现可能**无** GNU `timeout`；子任务需先 `grep timeout` 再按需删除，并在一行注释中写明「超时由上游 `macode-run` 负责」。

## 环境与验收（全体）

```bash
export PATH="/home/lenovo/pynoob/MaCode/bin:$PATH"
cd /home/lenovo/pynoob/MaCode
pytest tests/unit/test_inspect_conf.py -q   # S1-C 通过后必跑
python3 bin/cleanup-stale.py --dry-run      # S1-D 改前后均可
```

**不推荐**在子任务内默认跑完整 `macode render` 五场景（耗时）；S1-1 完成后可由人类或独立 CI 重跑 `docs/baseline/snapshot-*.json`。

## 子智能体 ID（最近一次启动后回填）

| 子任务 | Cursor Agent ID |
|--------|-----------------|
| S1-A | `c5939c5b-4639-4a97-b805-79e5bfa51ac3` |
| S1-B | `d8e0439e-bbb4-458a-87ff-d4d686ceadef` |
| S1-C | `c8f24fc9-3238-474f-9988-72d21ded8993` |
| S1-D | `62dfe79a-3775-409c-b7e9-69196d7012d3` |

## `macode-run` 超时读取约定

- 读取 `project.yaml` → `agent.resource_limits.max_render_time_sec`（缺省 600）。
- 解析失败或文件不存在时退回 600。
- 环境变量 `MACODE_TIMEOUT`（若 `isdigit()`）仍覆盖默认（与现有行为兼容）。

## `cleanup-stale.py --logs` 约定

- 仅处理 `.agent/log/*.log`（可递归或仅顶层，与现有目录结构一致）。
- 保留策略：**最近 200 个文件**（按 mtime）**或** **30 天内**；实现二选一或同时满足「删更旧者」——以 `refactor-todo` 原文为准。
- 支持 `--dry-run`；默认需显式 `--logs` 才删日志，避免误伤。

---

*主会话启动子任务后会把上表 Agent ID 填回此文件。*
