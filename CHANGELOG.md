# Changelog

## [Unreleased]
- Sprint 0 基线：见 docs/refactor-todo.md
- Sprint 3：Motion Canvas `serve.mjs` / `stop.mjs` / `playwright-render.mjs` / Browser Pool / guardian 合并为 `render.mjs`；`snapshot.mjs` 为薄封装 `--snapshot`；MC `engine.conf` 去掉 `service_script` 与端口字段
- Sprint 4：`engines/*/sourcemap.json` 为 api-gate 与 sync 的机器真源；`sourcemap-lint.py` 删除；jsonschema 校验；`macode sourcemap` 整合 generate-md / validate / scan-api / version-check；`api-gate` 支持 `--engine` 并与路径对齐
- Sprint 5：`bin/macode_layout` 统一 Zone/Narrative 校验与 mixin；`pipeline/_render/orchestrator.py` 承接单场景渲染；薄 `pipeline/render-scene.py` + `MACODE_USE_LEGACY_RENDER` 回滚；composite segment 直接调用 `render-scene.py`（后续 Sprint 6 移除 scene claim）
- Sprint 6（PRD）：不做 Multi-Agent — 删除 scene claim / exit 4–5 / `MACODE_AGENT_ID` / `MACODE_SKIP_SCENE_CLAIM` / `--no-claim`；`bin/macode_concurrency` 仅保留 `file_lock` + `write_json_atomic`；`cleanup-stale.py` 去掉 claim TTL；dashboard 移除 `/api/queue` 与 claimedBy；`macode-run` 不再写入 `agentId`

## 历史提交（最近 14 条）
- 2026-05-13 feat(checks): auto-trigger Layer 2 + SOURCEMAP gaps + check system hardening (89507a2)
- 2026-05-13 feat(security): TypeScript scene static analysis + doc corrections (56d5080)
- 2026-05-13 docs(AGENTS): v0.4 — fix outdated claims, add engine-specific caveats (6de3526)
- 2026-05-13 fix(lint): remove unused imports in sourcemap tools (a86ad08)
- 2026-05-13 docs(README): add developer notes for git hooks and protected primitives (f937f41)
- 2026-05-13 chore(git-hooks): versioned hook templates in .githooks/ with install-hooks.sh (5f3a246)
- 2026-05-13 feat(sourcemap): auto-update toolkit — version drift check, API gap scan, flat text sync (793f0bd)
- 2026-05-12 feat: MaCode Shader Preview — human monitoring extension for Layer 2 assets (84000ba)
- 2026-05-12 docs(shader-preview): adopt human_override.json for reject reasons (92e6bb5)
- 2026-05-12 docs: comprehensive MaCode Shader Preview design based on human monitoring primitives (15c2fbb)
- 2026-05-12 docs(README): restructure quick-start for Host-Agent-First (4e4feb5)
- 2026-05-12 chore: split setup into user vs dev editions (5b6ec40)
- 2026-05-12 release: 0.9.0 (1fa1c21)
- 2026-05-05 docs: update progress.md (Phase 5) and README.md (security + usage paths) (f6430f1)
