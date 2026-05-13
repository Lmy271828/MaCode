# Sprint 3 — Motion Canvas 合并（S3-1〜S3-2）

> **来源**：[`docs/refactor-todo.md` § Sprint 3](../refactor-todo.md)

## 执行策略（本会话）

Single-owner：**S3-1 与 S3-2** 同源修改 `render.mjs` / `snapshot` 委派，已由主会话顺序执行以避免冲突。

## 结果（主会话已交付）

- **S3-1**：新增 `render.mjs`（batch / `--serve-only` / `--stop` / `--snapshot`）；删除 `serve.mjs`、`stop.mjs`、`playwright-render.mjs`、`browser-pool.mjs`、`server-guardian.mjs`；`engine.conf` 去掉 `service_script`、`service_port_*`；`pipeline/render-scene.py` 对 `render_script` 以 `render.mjs` 结尾时走单次 `macode-run` + Node，不再拉起独立 service；`bin/macode` `mc serve|stop` 与 `dev.sh` 改调 `render.mjs`。
- **S3-2**：`snapshot.mjs` 保留为 **薄封装** → `render.mjs --snapshot …`（沿用原 CLI，满足 `rg snapshot.mjs` 与 `macode dev --snapshot` 路径）；`CHANGELOG`、`AGENTS.md`、cli-cheatsheet、`SOURCEMAP.md` 已同步。

**验收提示**：`pytest tests/unit/test_inspect_conf.py` 通过；**`wc -l` 全脚本**仍可能 >800（主要来自内联 `capture.ts` 模板）；若需压到 ≤800 可后续抽取模板到独立文件。

**环境说明**：若 `.venv` 中未安装 `PyYAML`，`render-scene` 会沿用 `get_python()` 选中的解释器导致 `inspect-conf` 失败——与本次改动无关，需在 venv 执行 `pip install pyyaml` 或修复 venv。
