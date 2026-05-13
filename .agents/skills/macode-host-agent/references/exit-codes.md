# MaCode CLI 退出码完整参考

## 渲染管道（pipeline/render.sh, render-scene.py）

| 退出码 | 含义 | 触发条件 | 处理建议 |
|--------|------|----------|----------|
| 0 | 成功 | 渲染完成，final.mp4 已生成 | 继续下一步 |
| 1 | 通用错误 | api-gate 拦截、引擎渲染失败、manifest 无效 | 查看日志，修复后重试 |
| 2 | retry | human_override.json action=retry | 按 instruction 修改后重试 |
| 3 | awaiting_review | review_needed 存在且无 override | 人工审批后继续（需 `--enable-review`，PRD D1 默认禁用） |

> **PRD D1 默认行为**：渲染默认 **不写** `review_needed` 标记，因此 exit 3 仅在 Host Agent 显式 `--enable-review` 后才可能出现。
>
> **Multi-Agent**：PRD 已移除 scene claim / 全局队列；不再有 exit 4/5。

## macode-run（统一进程生命周期管理器）

| 退出码 | 含义 | 触发条件 |
|--------|------|----------|
| 0 | 成功 | 子进程正常退出 |
| 非零 | 子进程退出码 | 原样传递 |
| 124 | 超时 | `timeout` 命令触发（macode-run 内部使用 SIGTERM→SIGKILL） |

## check-static.py / check-frames.py

| 退出码 | 含义 |
|--------|------|
| 0 | 全部通过（status: pass） |
| 1 | 发现问题（status: warning / error） |
| 2 | 配置错误（manifest 缺失等） |

## check-runner.py

| 退出码 | 含义 | 触发条件 |
|--------|------|----------|
| 0 | 全部通过 | 所有检查 status == pass |
| 1 | 只有 warning | 存在 warning 但无 error（Agent 可自行判断是否继续渲染） |
| 2 | 存在 error | 必须修复后才能渲染（如 source_missing、shader_missing） |

## api-gate.py

| 退出码 | 含义 |
|--------|------|
| 0 | 通过 |
| 1 | 发现 BLACKLIST 违规导入 |
| 2 | 参数错误（缺少 scene_file 或 sourcemap） |

## agent-run.sh（Git 包装器）

| 退出码 | 含义 |
|--------|------|
| 0 | 命令成功，已 git commit |
| 非零 | 命令失败，已 git checkout -- + git clean -fd 回滚 |

## 复合退出码

当命令通过管道执行时（如 `macode check | tee report.json`），退出码由最后一个命令决定。使用 `set -o pipefail` 可捕获管道中第一个失败命令的退出码。
