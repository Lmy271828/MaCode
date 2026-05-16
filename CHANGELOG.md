# Changelog

## [Unreleased]
- **文档**：新增 `docs/README.md` 索引；更新 `roadmap.md`、`adr-012`（当前 `render.mjs` 说明）、`narrative-integration-plan`、`test-plan`、`baseline/escape-hatches` 读法、`shader-preview-design` 进程段、`host-agent-skill-plan`（PRD 与 exit 码）；**未修改** `docs/progress.md`
- **R8-a / R8-c**：删除 `engines/motion_canvas/scripts/snapshot.mjs`，`dev.sh` 直调 `render.mjs --snapshot`；`docs/reduction-plan-deletion-risk.md` R8 节更新为已落地状态
- **R9-a / R9-c**：R9 清单与正文标注 `macode sourcemap` 单入口、四脚本正交保留；`AGENTS.md` §4.7 增补维护入口与「不再合并脚本」说明
- **S7 状态修正**：`docs/refactor-todo.md` 复测 README **426 行**、AGENTS **614 行**，S7-1/S7-2 标为部分完成
- Sprint 0 基线：见 docs/refactor-todo.md
- Sprint 3：Motion Canvas `serve.mjs` / `stop.mjs` / `playwright-render.mjs` / Browser Pool / guardian 合并为 `render.mjs`；MC `engine.conf` 去掉 `service_script` 与端口字段；**2026-05-13** 删除冗余 `snapshot.mjs`（`render.mjs --snapshot` 为唯一单帧入口）
- Sprint 4：`engines/*/sourcemap.json` 为 api-gate 与 sync 的机器真源；`sourcemap-lint.py` 删除；jsonschema 校验；`macode sourcemap` 整合 generate-md / validate / scan-api / version-check；`api-gate` 支持 `--engine` 并与路径对齐
- Sprint 5.1：`bin/macode_layout` 统一 Zone/Narrative 校验与 mixin
- Sprint 5.2：`pipeline/_render/{_paths,lifecycle,validate,engine,encode,orchestrator}.py` 真正拆分；orchestrator.py 118 行；composite-render 改用 `pipeline._render._paths` 的共享 helpers
- Sprint 6（PRD）：不做 Multi-Agent — 删除 scene claim / exit 4–5 / `MACODE_AGENT_ID` / `MACODE_SKIP_SCENE_CLAIM` / `--no-claim`；`bin/macode_concurrency` 仅保留 `file_lock` + `write_json_atomic`；`cleanup-stale.py` 去掉 claim TTL；dashboard 移除 `/api/queue` 与 claimedBy；`macode-run` 不再写入 `agentId`
- Sprint 7-CLEAN：S5-2 验收修复（orchestrator 拆分到位）、`progress-write` CLI 契约回归修复、测试 cwd 污染修复、`bin/macode` 默认引擎 fail-loud、project.yaml YAML 转义修复、新增 5 个 render stage 单测文件（27 用例）
- **PRD D1**：默认禁用 `review_needed` 标记 — orchestrator 默认 `--no-review` 行为；显式 `--enable-review` 才会写标记触发 exit 3 阻断流；`render_scene_legacy.py` 已删除（P0-1）
- **PRD D2 / P0-2**：composite 双轨合并 — `type: composite` 自动路由到 `composite-unified-render.py` 并发出 deprecation warning；`pipeline/composite-render.py` 已删除
- **S7 文档收敛（进行中）**：`AGENTS.md` 抽出深度参考到 `docs/architecture.md`；**行数 ≤500 仍为 S7-2 未结项目标**（见 `docs/refactor-todo.md` 复测）
- **S8 Scenes 卫生**：`test_self_correction*`、`test_layout_compiler` 从 `scenes/` 移到 `tests/fixtures/scenes/`；`tests/fixtures/scenes/README.md` 固化 `test_*` 前缀约定
- **Smoke/integration 脚本**：移除已废弃的 `--no-review`；`test_composite_render` 断言改为 unified 路径下的 `.agent/tmp/04_composite_demo/state.json`
- **`macode shader preview` 退役**：WebGL 预览脚本迁至 `experimental/shader-preview/shader-preview.mjs`；移除 `macode shader preview` / `preview-stop` 与 Dashboard 中 Shader Previews 分组；主路径仍以 `macode shader render` + 场景渲染为准

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
