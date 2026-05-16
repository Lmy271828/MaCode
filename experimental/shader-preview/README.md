# Shader Preview（experimental）

WebGL2 轻量预览服务已从 **`bin/` 与 `macode shader preview`** 退役，仅保留在此目录供本地实验。

**主 Path 仍推荐**：`python3 bin/shader-render.py <shader_dir>` 产出 PNG 帧 → Motion Canvas `ShaderFrame` 或 `macode dev` / `macode render` 走完整 Harness。

## 运行（非支持路径）

在仓库根目录：

```bash
node experimental/shader-preview/shader-preview.mjs <asset_id> [--port <n>]
```

示例：`lygia_circle_heatmap`（须存在于 `assets/shaders/_registry.json`）。

停止：向进程发送 SIGINT/SIGTERM，或根据 `.agent/tmp/shader-preview-<asset_id>/state.json` 中的 `pid` 执行 `kill`。

## 文档

设计背景与与人类监控原语的对齐说明见 [`docs/shader-preview-design.md`](../../docs/shader-preview-design.md)（文档内已标注 CLI 退役）。
