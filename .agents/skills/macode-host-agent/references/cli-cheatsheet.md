# MaCode CLI 完整速查表

## macode（主入口）

```bash
macode render <scene_dir> [--fps N] [--duration S] [--width W] [--height H]
macode check <scene_dir> [--static|--frames]
macode status
macode inspect --grep <regex>
macode composite info <scene_dir>
macode composite render <scene_dir>
macode composite init <scene_dir> --template <name>
macode composite add-segment <scene_dir> <seg_id> --after <ref>
macode mc serve <scene_dir> [--port N]
macode mc stop <scene_dir>
macode shader list
macode shader render <shader_dir>
macode sourcemap validate [engine|--all]
macode sourcemap generate-md [engine|--all]
macode sourcemap scan-api [--all|engine ...]
macode sourcemap version-check [--all]
macode test [unit|integration|smoke]
```

## pipeline/（直接调用）

```bash
pipeline/render.sh <scene_dir> [--json]
pipeline/render-scene.py <scene_dir> [--json] [--fps N] [--duration S]
pipeline/concat.sh <frames_dir> <out.mp4> [fps]
pipeline/add_audio.sh <video> <audio> <out>
pipeline/fade.sh <in.mp4> <out.mp4> [fade_in] [fade_out]
pipeline/compress.sh <in.mp4> <out.mp4>
pipeline/preview.sh <mp4>
pipeline/smart-cut.sh <mp4> <out.mp4>
pipeline/thumbnail.sh <mp4> <out.png> [time]
```

## bin/（工具脚本）

```bash
bin/render-all.sh [--parallel [N]] [scene_prefix]
bin/macode-run <task_id> [--timeout N] [--log <file>] [--tee] -- <command>
bin/agent-run.sh <scene_dir> <command> [args...]
bin/api-gate.py <scene_file> engines/<engine>/sourcemap.json [--engine <engine>]
bin/cleanup-stale.py [--dry-run] [--ttl N]
bin/dashboard-server.mjs [--port N]
bin/cache-key.py <scene_dir>
bin/cache-check.py <key>
bin/cache-store.py <key> <output_dir>
bin/cache-restore.py <key> <output_dir>
```

## engines/（引擎工具）

```bash
engines/manim/scripts/render.sh <scene.py> <out_dir> <fps> <duration> <w> <h>
engines/manim/scripts/inspect.sh
engines/motion_canvas/scripts/render.mjs <scene_dir> <frames_dir> <fps> <dur> <w> <h>   # batch
engines/motion_canvas/scripts/render.mjs --serve-only <scene_dir> [--port N]
engines/motion_canvas/scripts/render.mjs --stop <scene_dir>
engines/motion_canvas/scripts/snapshot.mjs <scene.tsx> <out.png> [t] [fps] [w] [h]
engines/motion_canvas/scripts/inspect.sh
```

## 检查脚本

```bash
bin/checks/duration_consistency.py --scene-dir <dir>
bin/checks/segment_consistency.py --scene-dir <dir>
bin/checks/duration_consistency.py --scene-dir <dir>
bin/checks/formula_density.py --scene-dir <dir>
bin/checks/shader_registry.py --scene-dir <dir>
bin/checks/layout_overlap.py --scene-dir <dir>

# 注册表方式（推荐）
bin/check-runner.py <scene_dir> [--layer layer1|layer2] [--format unified|raw]
bin/check-frames.py <scene_dir> [--output <file>]
```

## Dashboard API

```bash
GET /              → HTML 仪表盘
GET /api/state     → 全部场景状态 JSON
GET /api/scene/:name → 单个场景状态 JSON
GET /api/events    → SSE 实时流
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `MACODE_STATE_DIR` | macode-run 子进程状态目录 |
| `MACODE_TIMEOUT` | macode-run 默认超时（秒） |
| `MACODE_LOG_DIR` | 日志目录（默认 .agent/log） |
| `PROJECT_ROOT` | 项目根目录（render-scene.py 设置） |
