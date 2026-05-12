# Self-Correction Loop

## 目标

让 Agent 能够自动读取 check report，理解 issue，执行修复，重新验证，无需人类干预。

> **Note**: Layout-related checks (B1/B2/B3 overlap, boundary, readability) have been removed.
> The Layout Compiler now guarantees these via bounding-box contracts.
> Only temporal (A1/A2) and metadata checks remain.

---

## Check Report Schema v2

每个 issue 包含以下字段：

```json
{
  "type": "duration_mismatch",
  "message": "声明时长 3.00s 与计算动画时间 9.30s 偏差超过 0.5s",
  "suggested_lines": [10, 50],
  "fixable": true,
  "fix_confidence": 0.9,
  "fix": {
    "strategy": "adjust_wait",
    "action": "modify_wait_duration",
    "params": {
      "target_duration": 3.0,
      "current_duration": 9.3
    }
  }
}
```

### 关键字段

| 字段 | 含义 |
|------|------|
| `fixable` | 是否可以自动修复 |
| `fix_confidence` | 修复建议的可信度 (0.0–1.0) |
| `fix.strategy` | 修复策略类别 |
| `fix.action` | 具体动作 |
| `fix.params` | 修复所需参数 |

---

## 自动修复决策树

```
读取 check report
  │
  ├─ 所有 issue fixable=true 且 fix_confidence >= 0.8?
  │   ├─ YES → 自动修复
  │   └─ NO  → 请求人类确认
  │
  └─ 执行修复
       │
       ├─ 修改源码
       ├─ 清除渲染缓存（rm -rf .agent/tmp/{scene}/frames/）
       ├─ 重新 check
       └─ 重新 render
```

### 置信度阈值

| fix_confidence | 决策 |
|----------------|------|
| `>= 0.9` | 无条件自动修复 |
| `0.8 – 0.89` | 自动修复，但记录日志 |
| `0.6 – 0.79` | 请求人类确认 |
| `< 0.6` | 请求人类确认 |

---

## 按策略类型的修复方法

### strategy: `adjust_wait`（调整等待时间）

**场景**: `duration_mismatch` — 动画总时长与 manifest 声明不符

**修复**: 调整 `self.wait()` 或 `yield* waitFor()` 的时长

```python
# 修复前（Manim）
self.wait(5)  # 过长

# 修复后
self.wait(1.5)  # 调整至 target_duration - 其他动画时间
```

```tsx
// 修复前（Motion Canvas）
yield* waitFor(5);

// 修复后
yield* waitFor(1.5);
```

### strategy: `align_segment_comment`（同步 segment 元数据）

**场景**: `segment_missing` / `source_missing` / `comment_manifest_mismatch`

**修复**: 同步 manifest.json 与源码中的 `@segment` 注释

---

## 迭代控制

**最大迭代次数**: 3

如果同一场景连续 3 次 self-correction 后仍有 issue：
1. 停止自动修复
2. 创建 `review_needed` 信号：
   ```bash
   mkdir -p .agent/signals/per-scene/{scene_name}
   touch .agent/signals/per-scene/{scene_name}/review_needed
   ```
3. 在报告中说明失败原因

---

## 修复后必须做的事

1. **清除缓存**（否则可能使用旧帧）
   ```bash
   rm -rf .agent/tmp/{scene}/frames/
   ```

2. **重新 check 静态**（验证修改未引入新问题）
   ```bash
   macode check scenes/{scene}/
   ```

3. **重新渲染**（生成新帧）
   ```bash
   macode render scenes/{scene}/
   ```

---

## 人类介入触发条件

以下情况必须停止自动修复，请求人类确认：

- `fixable: false`
- `fix_confidence < 0.8`
- fix 策略是 `complex_refactor` 或 `redesign`
- 连续 3 次迭代未收敛
- 涉及删除已有内容（如删除 segment、删除公式）
- Git 状态异常（uncommitted changes 在 scene 目录外）

---

## 已移除的策略（由 Layout Compiler 保证）

以下策略在引入排版契约后不再需要：

| 旧策略 | 替换为 |
|--------|--------|
| `increase_buff` / `add_buff_parameter` | Layout Compiler 自动计算 zone 间距 |
| `adjust_position` / `clamp_to_canvas` | Bounding-box 契约保证元素在 safe zone 内 |
| `adjust_font` / `adjust_scale` / `clamp_font_size` | Design system 默认字号/缩放范围 |
| `adjust_color` / `adjust_background_or_formula_color` | 主题系统保证对比度 |
