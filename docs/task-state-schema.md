# MaCode 任务状态 JSON 约定

本文件描述写入 `.agent/tmp/<scene_or_task>/state.json` 的两类载荷。**读端**（如 `bin/dashboard-server.mjs`）应同时容忍 `version` 为 `1.0` 与 `1.1`（编排态），以及 **`macode-run` /Task** 的 v1.0 富形态。

## 编排态（Orchestration）— `macode_state.write_state`

- **写入方**：`pipeline/composite-render.py`、`pipeline/composite-unified-render.py` 等编排脚本。
- **`version`**：当前为 **`"1.1"`**（Sprint 2 起；与旧 `1.0` 文件可并存直至被下次写入覆盖）。
- **必选字段**：`taskId`（字符串，通常等于场景目录名）、`status`（`running` | `completed` | `failed` | `timeout`）、`exitCode`（整数）。
- **常见可选字段**：`startedAt`、`endedAt`（ISO 8601 字符串）、`outputs`（对象，可与旧 state 浅合并）、`error`（字符串；`completed` 成功时会清除）。
- **TypedDict**：`OrchestrationStateV11` 定义于 `bin/macode_state/__init__.py`，写入前经类型校验。

## Task 态（MaCode Task State）— `macode-run` 与 `bin/state-write.py`

- **写入方**：`bin/macode-run`（子命令生命周期）、`engines/*/scripts/render.sh` 通过 `state-write.py` 等。
- **`version`**：**`"1.0"`**（`state-write.py` / CLI 契约）。
- **额外常见字段**：`tool`、`cmd`（仅 `macode-run`）、`pid`、`durationSec`、`startedAt` / `endedAt`（`macode-run` 使用带偏移的 ISO）、嵌套 `outputs`、合并自子进程 `task.json` 的信息等。（历史文件可能仍含已弃用的 `agentId`。）
- **与编排态关系**：同一 `state.json` 路径上，**同一时间**只应有一类写入者占主导。

## 进度 JSONL

- **路径**：`.agent/progress/<scene>.jsonl`，每行一条 JSON。
- **字段**：`timestamp`（UTC，`…Z`）、`phase`、`status`；可选 `message` 及任意附加键（与 `render-scene.py` 一致，通过 `extra` 合并）。
