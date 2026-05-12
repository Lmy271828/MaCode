# MaCode 测试扩展规划

> 基于当前 9/9 smoke tests 全部通过的基础，系统性扩展测试金字塔。

## 1. 现状诊断

### 1.1 已有覆盖（Smoke）

| 区域 | 测试数 | 说明 |
|------|--------|------|
| Manim 渲染 | 2 | 单场景、参数覆盖 |
| Motion Canvas 渲染 | 3 | 单场景、dev server 生命周期、ShaderFrame |
| 复合/混合渲染 | 3 | composite、composite-unified、hybrid overlay |
| Manifest 验证 | 1 | 非法 manifest 拒绝 |

### 1.2 关键缺口

| 区域 | 风险等级 | 缺口说明 |
|------|----------|----------|
| Cache 工具链 | 🔴 高 | `cache-key/check/store/restore.py` 零测试 |
| `macode-run` | 🔴 高 | 进程生命周期、超时、signal forwarding、task.json 合并 |
| 音频管道 | 🟡 中高 | `add_audio.sh`, `audio-analyze.sh`, `composite-audio*.py` |
| Cache 命中路径 | 🟡 中高 | 当前每次 `cleanup_tmp` 清空 cache，无二次渲染验证 |
| `inspect-conf.py` | 🟡 中 | 刚提取，yq/grep 双路径无覆盖 |
| `copilot-feedback.py` | 🟡 中 | 终端 raw mode 难以自动化，需隔离测试 |
| 跨引擎一致性 | 🟡 中 | 输出格式、progress.jsonl、state.json  schema 合规 |
| 边界/异常 | 🟡 中 | 端口占用、引擎崩溃、超时、信号中断 |
| `macode` CLI | 🟢 低 | `status`, `check`, `dev` 等子命令 |
| 交付/压缩 | 🟢 低 | `deliver.sh`, `compress.sh` |

---

## 2. 测试架构设计

### 2.1 三层金字塔

```
        ┌─────────────┐
        │   Smoke     │  ← 端到端渲染验证（已有，~5min）
        │  (~9 tests) │
        ├─────────────┤
        │ Integration │  ← 工具链组合、cache 命中、server 生命周期（新增）
        │  (~15-20)   │
        ├─────────────┤
        │    Unit     │  ← 纯函数、独立模块、schema 验证（新增）
        │  (~30-40)   │
        └─────────────┘
```

### 2.2 技术选型

| 层级 | 框架 | 理由 |
|------|------|------|
| Unit | **pytest** | Python 生态、快速（<1s）、易于 mock |
| Integration | **bash + lib.sh** | 与现有 smoke 框架一致、测试真实 shell 调用 |
| Smoke | **bash + lib.sh** | 已有框架，继续沿用 |

**混合策略**：单元测试用 pytest 跑纯函数；集成/端到端用 bash 跑真实工具。

---

## 3. 分阶段实施计划

### Phase 1：单元测试骨架（Unit Layer）

**目标**：为所有 `bin/*.py` 纯工具建立 pytest 骨架， CI 中 `<10s`。

**具体任务**：

| # | 任务 | 验证点 | 优先级 |
|---|------|--------|--------|
| 1.1 | `tests/unit/test_cache_key.py` | 哈希稳定性、排除规则、空目录处理、跨平台路径 | P0 |
| 1.2 | `tests/unit/test_inspect_conf.py` | yq 路径、grep 回退路径、缺失文件回退、整数字段 | P0 |
| 1.3 | `tests/unit/test_state_schema.py` | task-state-schema v1 合规验证器 | P1 |
| 1.4 | `tests/unit/test_signal_check.py` | 信号文件解析、per-scene 状态机 | P1 |
| 1.5 | `tests/unit/test_composite_init.py` | manifest 分段解析、默认填充 | P1 |

**CI 集成**：
```yaml
# .github/workflows/ci.yml 新增 job
- name: Unit tests
  run: pytest tests/unit/ -v --tb=short
```

---

### Phase 2：Cache 与生命周期集成测试

**目标**：覆盖当前最大缺口——cache 工具链和 `macode-run`。

#### 2A. Cache 工具链集成（`tests/integration/test_cache.sh`）

```bash
test_cache_key_idempotent() {
    # 同一目录两次计算，key 必须相同
}
test_cache_hit_miss_cycle() {
    # 1. cache-key → 2. cache-check (miss) → 3. cache-store → 4. cache-check (hit) → 5. cache-restore
}
test_cache_restore_preserves_structure() {
    # 恢复后目录结构、文件内容与原目录一致
}
test_cache_key_excludes_ignored() {
    # 修改 .log / node_modules / __pycache__ 不改变 key
}
```

#### 2B. `macode-run` 集成（`tests/integration/test_macode_run.sh`）

```bash
test_macode_run_success_merges_task_json() {
    # 子进程写 task.json → macode-run 合并到 state.json["outputs"]
}
test_macode_run_timeout_sigterm() {
    # 子进程 sleep 100，timeout 1s → 收到 SIGTERM，state.json status="timeout"
}
test_macode_run_signal_forwarding() {
    # 向 macode-run 发 SIGINT → 子进程也收到
}
test_macode_run_missing_task_json() {
    # 子进程不写 task.json → state.json 正常，outputs 为空
}
```

#### 2C. Cache 命中端到端（`tests/smoke/test_cache_hit.sh`）

```bash
test_manim_cache_hit() {
    # 第一次渲染（miss）→ 第二次渲染（hit）→ 第二次耗时显著降低 / 直接复用
}
```

---

### Phase 3：边界与异常测试

**目标**：覆盖错误路径，防止回归。

| # | 场景 | 测试文件 |
|---|------|----------|
| 3.1 | 端口占用时 `find_free_port` 应跳过已被占用的端口 | `test_render_mc.sh` 新增 |
| 3.2 | 引擎进程崩溃（SIGKILL）时 `render-scene.py` 正确标记 failed | `test_render_manim.sh` 新增 |
| 3.3 | 非法 `engine.conf`（缺少 render_script）优雅降级 | `test_inspect_conf.sh` |
| 3.4 | `manifest.json` 缺少必填字段（engine、version） | 已有 `test_manifest_validation_fail`，扩展更多 case |
| 3.5 | Shader asset `manifest.json` 缺失 `frame_count` 字段 → fallback 到扫描 | `test_mc_shaderframe.sh` |
| 3.6 | 并发渲染两个不同场景，port 不冲突 | `test_render_mc.sh` 新增 |

---

### Phase 4：跨引擎一致性契约测试

**目标**：所有引擎输出满足统一契约，便于上层编排器无差别处理。

| 契约 | 验证方式 |
|------|----------|
| `state.json` 必须符合 task-state-schema v1 | pytest schema validator |
| `progress.jsonl` 必须包含 `phase: "completed"` | `assert_progress_phases` |
| 最终 `final.mp4` 必须存在且非空 | `assert_file_exists` + `assert_file_not_empty` |
| 帧目录 PNG 数量 ≈ fps × duration（容差 ±1） | `assert_frame_count` |

**实现**：创建 `tests/contract/` 目录，每个引擎一个测试文件，只验证上述契约，不验证渲染内容。

---

### Phase 5：性能与压力测试（可选 / 未来）

| # | 场景 | 目的 |
|---|------|------|
| 5.1 | 连续渲染 10 个场景，验证无端口泄漏 | 防止 `serve.mjs` 残留 |
| 5.2 | Cache 存储 100 个场景，恢复第 50 个 | 验证 cache 规模线性扩展 |
| 5.3 | 大 manifest（100 个分段）composite 渲染 | 验证内存/时间可接受 |

---

## 4. 目录结构规划

```
tests/
├── unit/                       # pytest 单元测试（Phase 1）
│   ├── __init__.py
│   ├── conftest.py             # fixtures: tmp_scene_dir, fake_engine_conf
│   ├── test_cache_key.py
│   ├── test_inspect_conf.py
│   ├── test_state_schema.py
│   └── test_composite_init.py
├── integration/                # bash 集成测试（Phase 2）
│   ├── lib.sh                  # 共享断言（可引用 smoke/lib.sh）
│   ├── test_cache.sh
│   ├── test_macode_run.sh
│   └── test_audio_pipeline.sh
├── contract/                   # 跨引擎契约测试（Phase 4）
│   ├── test_manim_contract.sh
│   └── test_mc_contract.sh
└── smoke/                      # 端到端（已有 + Phase 3 扩展）
    ├── lib.sh
    ├── runner.sh
    ├── test_render_manim.sh
    ├── test_render_mc.sh
    ├── test_composite.sh
    └── test_cache_hit.sh       # Phase 2C
```

---

## 5. CI/CD 规划

```yaml
# .github/workflows/ci.yml
jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.13' }
      - run: pip install pytest
      - run: pytest tests/unit/ -v

  integration:
    runs-on: ubuntu-latest
    needs: unit
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.13' }
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: sudo apt-get install -y ffmpeg jq
      - run: pip install -r requirements.txt
      - run: npm ci
      - run: bash tests/integration/runner.sh --verbose

  smoke:
    runs-on: ubuntu-latest
    needs: integration
    steps:
      # 已有 workflow，保持不变
      - run: ./bin/macode test smoke --verbose
```

---

## 6. 近期可立即执行的 3 件事

以下任务可以**立刻开始**，每个任务独立、不互相阻塞：

### 任务 A：Cache 工具链单元 + 集成测试（~2h）
- `tests/unit/test_cache_key.py`：验证哈希稳定性、排除规则
- `tests/integration/test_cache.sh`：验证 store/restore/check 完整周期
- **价值**：当前最大缺口，cache 是性能核心

### 任务 B：`macode-run` 集成测试（~1.5h）
- `tests/integration/test_macode_run.sh`：timeout、signal forwarding、task.json 合并
- **价值**：进程生命周期管理器是整个管线的根基

### 任务 C：Smoke Cache 命中测试（~1h）
- `tests/smoke/test_cache_hit.sh`：同一场景渲染两次，第二次走 cache
- **价值**：验证 cache 集成到 render 路径的端到端效果

---

## 7. 度量指标

| 指标 | 当前 | 目标（Phase 1-4 完成后） |
|------|------|-------------------------|
| 总测试数 | 9 | ≥ 40 |
| Unit 测试数 | 0 | ≥ 15 |
| 集成测试数 | 0 | ≥ 10 |
| 端到端测试数 | 9 | ≥ 15 |
| CI 总时长 | ~5min | ~7min（unit 10s + integration 2min + smoke 5min） |
| 行覆盖率 | ~15%（仅 smoke 路径） | ≥ 60%（bin/ + pipeline/ 核心工具） |

---

*文档版本: 0.1*  
*日期: 2026-05-10*
