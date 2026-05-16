# 已删除组件墓碑

本文件记录 MaCode 项目中已被彻底删除的组件，防止未来开发者误以为是"遗漏"或"误删"而尝试恢复。

> **规则**：删除一个组件后，如果该组件的名字曾在文档、注释、测试数据中被广泛引用，则应在本文档中新增一行墓碑记录。

---

## 安全模型（P0-A，2026-05）

| 组件 | 删除时间 | 删除原因 | 替代方案 |
|------|---------|---------|---------|
| `bin/sandbox-check.py` | 2026-05 | 象征性执行，从未真正隔离不可信代码；绕过成本为零 | `api-gate.py` + Git hooks（诚实且轻量） |
| `bin/primitive-gate.py` | 2026-05 | 检测手写 GLSL/raw LaTeX/ffmpeg filtergraph，误报率高，无实际拦截价值 | 无（依赖 code review 和 SKILL 约束） |
| `bin/fs-guard.py` | 2026-05 | 检查场景目录边界，但所有合法操作已在 AGENTS.md 中约束 | AGENTS.md 反模式清单 + pre-commit hook |
| `bin/security-run.sh` | 2026-05 | 薄分发器，并行调用上述三个已删除的检查器 | `api-gate.py` 单独执行 |
| `bin/security-advise.py` | 2026-05 | 安全建议生成器，输出从未被消费 | 无（删除与诚实化同期完成） |
| `.agents/skills/security-guardian/` | 2026-05 | Security Guardian skill，基于已删除的安全脚本 | 无（安全策略在 AGENTS.md §5 中诚实描述） |

## Composite 遗产（P0-B，2026-05）

| 组件 | 删除时间 | 删除原因 | 替代方案 |
|------|---------|---------|---------|
| `pipeline/composite-assemble.py` | 2026-05 | Composite 过度设计，支持转场/音频/叠加但实际未使用 | `composite-unified-render.py`（仅硬切拼接） |
| `pipeline/composite-audio.py` | 2026-05 | 同上 | `pipeline/add_audio.sh`（独立 ffmpeg 脚本） |
| `pipeline/composite-audio-sync.py` | 2026-05 | 同上 | 无（音频同步由场景代码直接处理） |
| `pipeline/composite-cache.py` | 2026-05 | 同上 | 无（composite 无缓存需求） |
| `pipeline/composite-overlay.py` | 2026-05 | 同上 | 无（叠加在场景代码中用 Manim 动画实现） |
| `pipeline/composite-transition.py` | 2026-05 | 同上 | 无（转场由 `pipeline/concat.sh` 硬切，或场景代码中实现） |

## 僵尸组件（P1-A，2026-05）

| 组件 | 删除时间 | 删除原因 | 替代方案 |
|------|---------|---------|---------|
| `bin/dashboard-server.mjs` | 2026-05 | 523 行实时仪表盘，无人使用，维护成本高 | `tail -n 20 .agent/progress/*.jsonl` |
| `bin/timeline-generator.py` | 2026-05 | 171 行时间线生成器，无消费端 | 无（时间线由 `pipeline/audio-analyze.sh` 输出 CSV） |
| `bin/report-generator.py` | 2026-05 | 266 行报告生成器，输出从未被查看 | 无（删除与扁平化同期完成） |

## 检查链路（P1-B，2026-05）

| 组件 | 删除时间 | 删除原因 | 替代方案 |
|------|---------|---------|---------|
| `bin/check-frames.py` | 2026-05 | CV 质检工具，与 `check-static.py` 功能重叠 | `check-static.py --layer layer2` |

## 缓存系统（2026-05-17）

| 组件 | 删除时间 | 删除原因 | 替代方案 |
|------|---------|---------|---------|
| `pipeline/cache.sh` | 2026-05-17 | 向后兼容适配层，底层工具链从未命中缓存 | 无（透明渲染优先于缓存优化） |
| `bin/cache-key.py` | 2026-05-17 | 计算 SHA-256 缓存键，但缓存目录始终为空 | 无 |
| `bin/cache-check.py` | 2026-05-17 | 检查缓存命中，验证逻辑薄弱（仅查文件存在） | 无 |
| `bin/cache-store.py` | 2026-05-17 | 存储输出到缓存目录 | 无 |
| `bin/cache-restore.py` | 2026-05-17 | 从缓存恢复输出 | 无 |

## 状态系统（2026-05-17）

| 组件 | 删除时间 | 删除原因 | 替代方案 |
|------|---------|---------|---------|
| `macode_state.write_task_state_v1_from_cli()` | 2026-05-17 | v1.0 双轨制导致同一文件两种 schema | `macode_state.write_state_to_path()`（统一 v1.1） |

## 已删除的 manifest 字段（P1-D，2026-05）

以下字段从 `scenes/*/manifest.json` 及文档中移除，不再被任何代码解析：

| 字段 | 原用途 | 删除原因 |
|------|--------|---------|
| `transition` | Composite segment 间转场效果 | 实际仅支持硬切，虚假承诺 |
| `audio` | Composite 全局音轨配置 | 由独立 `pipeline/add_audio.sh` 处理 |
| `overlays` | Composite 叠加层 | 在场景代码中用 Manim 实现 |

---

*维护者：删除新组件时，请按上述格式追加一行，并在提交信息中引用本文件。*
