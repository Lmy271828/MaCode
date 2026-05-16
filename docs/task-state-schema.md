# MaCode 任务状态 JSON 约定

本文件描述写入 `.agent/tmp/<scene_or_task>/state.json` 的统一载荷格式。

**版本**：`1.1`（OrchestrationState）

**写入方**：`pipeline/composite-unified-render.py`、`bin/macode-run`、`bin/state-write.py` 等全部统一走 `macode_state.write_state_to_path()`。

**读取方**：`bin/state-read.py`、`pipeline/deliver.py`、任意 `jq`/`cat` 工具。

## 必选字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `version` | `string` | 固定为 `"1.1"` |
| `taskId` | `string` | 任务标识（通常等于场景目录名） |
| `status` | `string` | `running` \| `completed` \| `failed` \| `timeout` |
| `exitCode` | `int` | 进程退出码（`running` 时通常为 `0`） |

## 常见可选字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `startedAt` | `string` | ISO 8601 开始时间戳 |
| `endedAt` | `string` | ISO 8601 结束时间戳（终端状态才有） |
| `outputs` | `object` | 任意键值对，新写入会与旧 state 浅合并 |
| `error` | `string` | 错误信息；`completed` 成功时会自动清除 |

## 扩展字段（历史 v1.0 兼容）

以下字段由 `macode-run` / CLI 工具写入，属于 v1.1 的扩展：

| 字段 | 类型 | 说明 |
|------|------|------|
| `cmd` | `string[]` | macode-run 执行的原始命令数组 |
| `pid` | `int` | 子进程 PID |
| `durationSec` | `number` | 墙钟运行时长（秒） |
| `tool` | `string` | 工具名称（如 `render.sh`） |

## TypedDict

`OrchestrationStateV11` 定义于 `bin/macode_state/__init__.py`，写入前经 `_validate_orchestration` 校验。

## 进度 JSONL

- **路径**：`.agent/progress/<scene>.jsonl`，每行一条 JSON。
- **字段**：`timestamp`（UTC，`…Z`）、`phase`、`status`；可选 `message` 及任意附加键（与 `render-scene.py` 一致，通过 `extra` 合并）。
