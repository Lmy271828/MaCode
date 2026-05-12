# 面向 Host Agent 的画面自纠工具设计

> 状态：设计草案  
> 日期：2026-05-10  
> 背景：现有 check-static/check-frames 只检测不修复，human_override 只审批不自纠

---

## 1. 核心问题

当前系统的质量闭环是：**检测 → 报告 → 人工决策 → 人工修复 → 重渲染**。

Host Agent 收到 check-static 的 `duration_mismatch` 后，只能把自然语言 message 传给 LLM 去"猜测"如何修复。这导致：
- 修复不可预测（LLM 可能改错位置）
- 成本高（每帧问题都触发 LLM 调用）
- 无法验证（修复后是否真解决了问题）

**目标**：让检测报告包含**可执行的修复指令**，Agent 无需 LLM 即可自动修复 80% 的常见问题。

---

## 2. 架构设计

### 2.1 三层模型

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Orchestrator (auto-fix.py)                        │
│  - 调度检测 → 诊断 → 修复 → 验证的闭环                        │
│  - 防死循环（最大轮次限制）                                   │
│  - 不可修复问题降级到 review_needed                          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Strategies (fix-strategies/*.py)                  │
│  - 纯函数：Issue → Patch                                     │
│  - 每个策略声明支持的 issue type 和置信度                     │
│  - 策略之间无状态依赖                                         │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Detectors (check-static.py / check-frames.py)     │
│  - 输出 Schema v2（增加 fixable + fix 字段）                 │
│  - 保持向后兼容（旧字段不动）                                  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 报告 Schema v2

在现有 JSON 基础上，每个 issue 增加三个字段：

```json
{
  "type": "duration_mismatch",
  "severity": "warning",
  "message": "声明时长 5.00s 与计算动画时间 7.00s 偏差超过 0.5s",
  "suggested_lines": [37, 65],
  
  "fixable": true,
  "fix_confidence": 0.95,
  "fix": {
    "strategy": "adjust_wait",
    "target": {
      "file": "scene.py",
      "lines": [37, 65]
    },
    "action": "replace_pattern",
    "pattern": "self\.wait\(([^)]+)\)",
    "replacement_template": "self.wait({new_value})",
    "params": {
      "old_value": 2.0,
      "new_value": 3.5,
      "unit": "seconds",
      "delta": "+1.5"
    },
    "rollback_info": {
      "backup_marker": "# AUTO-FIX: adjusted wait from 2.0 to 3.5"
    }
  }
}
```

**关键设计决策**：
- `fixable`：布尔值，明确告知 Agent 这个问题是否可以自动修复
- `fix_confidence`：0-1 之间，低置信度（<0.8）的问题即使 `fixable=true` 也建议走 LLM 路径
- `action`：统一为有限的操作集（`replace_pattern`, `insert_before`, `delete_lines`, `append_param`），避免 Turing-complete 的任意代码修改

### 2.3 策略接口

```python
# bin/fix-strategies/_base.py
from typing import Protocol, TypedDict
from dataclasses import dataclass

class Patch(TypedDict):
    file: str
    line_start: int
    line_end: int
    old_text: str
    new_text: str

@dataclass
class FixResult:
    success: bool
    patches: list[Patch]
    message: str
    verification_hint: str   # 修复后如何验证（如 "重新运行 calc_animation_time"）

class FixStrategy(Protocol):
    """修复策略协议。"""
    
    @property
    def supported_types(self) -> set[str]:
        """此策略能处理的 issue type 集合。"""
        ...
    
    def can_fix(self, issue: dict, scene_dir: str) -> tuple[bool, float]:
        """判断是否能修复此 issue，返回 (能否修复, 置信度)。"""
        ...
    
    def apply(self, issue: dict, scene_dir: str) -> FixResult:
        """执行修复，返回 Patch 列表。"""
        ...
```

### 2.4 内置策略库

| 策略文件 | 支持的 issue type | 修复动作 |
|----------|-------------------|----------|
| `adjust_wait.py` | `duration_mismatch` | 修改 `self.wait()` 参数值 |
| `increase_buff.py` | `overlap` | 在 `VGroup.arrange()` 等调用中增大 `buff=` |
| `adjust_color.py` | `formula_unreadable` | 修改 `MathTex(color=...)` 为对比度更高的颜色 |
| `split_formula.py` | `formula_density` | 拆分过长的 `MathTex` 为多个 |
| `align_segment_comment.py` | `comment_manifest_mismatch` | 同步 manifest.json 和源码注释的时间字段 |

### 2.5 闭环工作流

```
渲染完成
    │
    ▼
┌─────────────────┐
│ 运行检测器       │
│ (static+frames) │
└─────────────────┘
    │
    ▼
是否存在 fixable=true 且 confidence>0.8 的 issue？
    │
    ├── 否 ──→ 所有问题不可自动修复 ──→ 标记 review_needed
    │
    ▼ 是
┌─────────────────┐
│ 按优先级排序     │
│ (severity 高优先)│
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 应用修复策略     │
│ (生成 Patch)     │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 应用 Patch       │
│ (修改源码)       │
│ + 创建 git stash │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 重新渲染         │
│ (限制 fps/dur)   │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ 重新检测         │
│ (仅验证修改的     │
│  segment)       │
└─────────────────┘
    │
    ▼
原 issue 是否消失？
    │
    ├── 是 ──→ 进入下一轮（检查剩余 fixable issue）
    │            │
    │            ▼ 达到 max_rounds（默认 3）
    │            标记 review_needed（人工复核）
    │
    └── 否 ──→ 回滚 Patch（git stash pop）
              标记 review_needed
```

**防死循环设计**：
- `max_rounds = 3`：同一 scene 最多自动修复 3 轮
- `fps_limit = 5`：修复验证渲染时降低 fps，减少时间
- `duration_limit = 2`：验证渲染最多 2 秒

### 2.6 与现有系统的集成点

**方案 A：渲染后自动触发**（激进）

修改 `pipeline/render-scene.py`，在渲染完成后、标记 review_needed 之前插入自纠逻辑：

```python
# render-scene.py 渲染完成后
if not args.no_auto_fix:
    auto_fix_result = run_auto_fix(scene_dir, max_rounds=3)
    if auto_fix_result.has_unfixable_issues:
        review_path.touch()  # 仍有不可修复问题，标记人工审核
```

**方案 B：独立 CLI 命令**（保守，推荐）

新增 `macode fix <scene_dir>`，由 Host Agent 显式调用：

```bash
macode fix scenes/01_test --max-rounds 3 --verify-fps 5
```

**推荐方案 B**：
- 不侵入现有渲染流程
- Host Agent 可以决定是否启用自纠（根据场景复杂度）
- 便于单独测试和迭代

---

## 3. 实施路线图

### Phase 1：Schema 升级（1-2 小时）

修改 `check-static.py` 和 `check-frames.py`：
1. 所有 `issues.append()` 处增加 `severity` 字段
2. 高频 issue type 增加 `fixable` + `fix` 字段
3. 低频 issue type 设置 `fixable: false`

**优先级**：`duration_mismatch` > `overlap` > `formula_unreadable`

### Phase 2：策略框架（2-3 小时）

1. 创建 `bin/fix-strategies/_base.py`（协议定义）
2. 创建 `bin/auto-fix.py`（编排器）
3. 实现第一个策略 `adjust_wait.py`

### Phase 3：闭环验证（2-3 小时）

1. `macode fix` CLI 命令集成
2. 修复 → 渲染 → 检测的集成测试
3. 回滚逻辑测试

### Phase 4：扩展策略（按需）

逐个实现 `increase_buff.py`、`adjust_color.py` 等。

---

## 4. 风险与回退

| 风险 | 缓解措施 |
|------|----------|
| 自动修复破坏源码语法 | 修复前 `git stash`，失败时回滚 |
| 修复引入新问题 | 修复后重新运行 api-gate + check-static |
| 无限循环（修复 A 导致 B，修复 B 导致 A） | `max_rounds` 限制 |
| 修复后画面质量反而下降 | 人工审核兜底（review_needed） |

---

## 5. 示例：完整自纠闭环

**初始状态**：
```python
# scene.py
# @segment:main
# @time:0.0-5.0s
def construct(self):
    c = Circle()
    self.play(Create(c), run_time=3.0)
    self.wait(2.5)   # ← 总时间 5.5s，声明 5.0s
```

**检测输出**（Schema v2）：
```json
{
  "type": "duration_mismatch",
  "fixable": true,
  "fix": {
    "strategy": "adjust_wait",
    "action": "replace_pattern",
    "pattern": "self\.wait\(([^)]+)\)",
    "params": {"old_value": 2.5, "new_value": 2.0, "delta": "-0.5"}
  }
}
```

**修复后**：
```python
self.wait(2.0)   # ← 自动修改
```

**重新检测**：`calc_animation_time = 5.0s`，偏差 0，通过。
