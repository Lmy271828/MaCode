# MaCode Task State v1.0

**Status**: Draft  
**Date**: 2026-05-10  
**Scope**: All execution-layer tools in MaCode Harness 2.0

---

## Design Principles

1. **Transparency over Convenience**: State files are plain JSON. Read them with `cat`, `jq`, or `python -c "import json"`. No binary formats, no hidden caches.
2. **Do One Thing**: Each tool writes exactly one state file describing its own completion. It does not manage other tools' states.
3. **Text Streams**: State files are line-oriented JSON (one object per file). Future versions may use JSONL for append-only progress.

---

## File Location Convention

```
.agent/tmp/{task_id}/state.json   — written by macode-run (lifecycle manager)
.agent/tmp/{task_id}/task.json    — written by the execution tool itself (optional)
```

If a tool is wrapped by `macode-run`, the tool may write `task.json` in the same directory. `macode-run` merges `task.json` into `state.json["outputs"]` on completion.

If a tool runs standalone (e.g. `macode mc serve`), it writes `state.json` directly.

---

## Schema

```json
{
  "$schema": "https://macode.dev/schemas/task-state-v1.json",
  "version": "1.0",
  "tool": "serve.mjs",
  "taskId": "01_test_mc-service",
  "status": "completed",
  "exitCode": 0,
  "startedAt": "2026-05-10T12:00:00Z",
  "endedAt": "2026-05-10T12:00:05Z",
  "durationSec": 5.0,
  "outputs": {
    "port": 4567,
    "captureUrl": "http://localhost:4567/engines/motion_canvas/capture.html"
  },
  "error": null
}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Always `"1.0"` |
| `tool` | string | Tool name (e.g. `"serve.mjs"`, `"playwright-render.mjs"`) |
| `status` | string | `"running"` \| `"completed"` \| `"failed"` \| `"timeout"` |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `taskId` | string | Assigned by orchestrator (e.g. `"01_test_mc-service"`) |
| `exitCode` | integer \| null | Process exit code. `null` if killed by signal. |
| `startedAt` | string (ISO 8601) | Start timestamp |
| `endedAt` | string (ISO 8601) | End timestamp |
| `durationSec` | number | Wall-clock duration in seconds |
| `outputs` | object | Tool-specific outputs. Schema is tool-defined. |
| `error` | string \| null | Human-readable error message if `status == "failed"` |

### Outputs Convention

Each tool documents its own `outputs` keys in its header comment. Examples:

**serve.mjs**:
```json
{"outputs": {"port": 4567, "captureUrl": "http://localhost:4567/..."}}
```

**playwright-render.mjs**:
```json
{"outputs": {"framesRendered": 60, "outputDir": ".agent/tmp/01_test_mc/frames"}}
```

**shader-prepare.mjs**:
```json
{"outputs": {"shadersChecked": 2, "shadersRendered": 1}}
```

---

## Orchestrator Consumption

The orchestrator (`render-scene.py`) reads `state.json` and accesses tool outputs via:

```python
state = json.load(open(state_path))
outputs = state.get("outputs", {})
port = outputs.get("port")
capture_url = outputs.get("captureUrl")
```

The orchestrator **must not** assume the existence of specific output keys unless the engine.conf declares them.

---

## Migration from Pre-v1 Formats

Pre-v1 tools wrote ad-hoc state files with tool-specific top-level keys (e.g. `serve.mjs` wrote `{pid, port, captureUrl}` at the top level). Migration path:

1. Move tool-specific keys into `outputs` object.
2. Add `version: "1.0"`, `tool`, and `status` fields.
3. Keep top-level `pid` only if it is the actual OS process ID (lifecycle concern, not tool output).

---

## Reference Implementation

MaCode provides CLI wrappers so engine scripts do not need inline Python/Node to write state files.

### `bin/state-write.py`

Generates or updates a v1.0 `state.json` with atomic writes (`.tmp` → `os.replace`).

```bash
state-write.py <state_dir> <status> [exit_code]
    [--tool NAME] [--outputs JSON] [--error MSG]
    [--started-at ISO] [--ended-at ISO] [--duration SEC]
    [--task-id ID]
```

**Features:**
- **Atomic write**: `state.json.tmp` → `os.replace` to `state.json`.
- **Merge semantics**: If `state.json` already exists, existing `startedAt`, `outputs`, and `taskId` are preserved unless overwritten.
- **Auto timestamps**: `startedAt` is set on `running`; `endedAt` and `durationSec` are set on terminal statuses (`completed`/`failed`/`timeout`).
- **Outputs merge**: New `--outputs` keys are merged into existing `outputs` (new keys win).

**Engine usage example** (from `engines/*/scripts/render.sh`):
```bash
write_state() {
    local status="$1"
    shift
    "$PROJECT_ROOT/bin/state-write.py" "$STATE_DIR" "$status" --tool "render.sh" "$@" 2>/dev/null || true
}

write_state "running" --task-id "$SCENE_NAME"
write_state "completed" 0 --outputs '{"framesRendered": 90}'
write_state "failed" 1 --error "ModuleNotFoundError"
```

### `bin/progress-write.py`

Appends a JSONL record to `.agent/progress/{scene}.jsonl`.

```bash
progress-write.py <progress_file> <phase> <status> [message]
```

**Engine usage example:**
```bash
write_progress() {
    local phase="$1"
    local status="$2"
    local msg="${3:-}"
    "$PROJECT_ROOT/bin/progress-write.py" \
        "$PROJECT_ROOT/.agent/progress/${SCENE_NAME}.jsonl" \
        "$phase" "$status" "$msg" 2>/dev/null || true
}

write_progress "init" "running" "Render starting"
write_progress "render" "completed" "90 frames"
```

### `bin/state-read.py`

Reads `state.json` with optional field extraction.

```bash
state-read.py <state_dir> [--field FIELD] [--jq EXPR]
```

Examples:
```bash
state-read.py .agent/tmp/01_test --field status        # → completed
state-read.py .agent/tmp/01_test --jq .outputs.port    # → 4567
```

---

## Future Versions

- **v1.1**: Add `artifacts` array for output file manifests (frame sequences, MP4s, etc.)
- **v2.0**: Switch to JSONL for append-only progress streams (merge with `progress.jsonl`)
