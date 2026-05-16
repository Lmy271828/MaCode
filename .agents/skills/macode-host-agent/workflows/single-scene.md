# 单场景完整工作流

## 目标

从零开始创建并渲染一个 MaCode 场景，包含 check → fix → render → re-check 的完整循环。

---

## Phase 1: 需求分析

```bash
# 1. 读取项目配置
cat project.yaml

# 2. 读取场景目录结构
ls scenes/

# 3. 确定新场景名称（序号前缀保证拼接顺序）
# 例如：scenes/05_new_scene/
```

---

## Phase 2: 创建 Manifest

创建 `scenes/05_new_scene/manifest.json`：

```json
{
  "engine": "manim",
  "duration": 5,
  "fps": 30,
  "resolution": [1920, 1080],
  "segments": [
    {"id": "intro", "line_start": 1, "line_end": 50}
  ]
}
```

**关键字段**：
- `engine`: `manim` | `motion_canvas` | `manimgl`
- `duration`: 总时长（秒），必须与动画时间匹配
- `fps`: 正整数
- `resolution`: `[width, height]`

---

## Phase 3: 查询 API

```bash
# 搜索你想用的图形/动画 API
macode inspect --grep "Circle\|Square\|Line"

# 搜索文本/公式
macode inspect --grep "MathTex\|Tex"

# 搜索变换动画
macode inspect --grep "Transform\|Create"
```

**不要**直接 `grep -r` 整个引擎源码树。使用 `macode inspect`。

---

## Phase 4: 编写源码

### Manim 示例

创建 `scenes/05_new_scene/scene.py`：

```python
from manim import *

# @segment:intro
# @time:0.0-5.0s
# @keyframes:[0.0, 2.5, 5.0]
# @description:Demo scene with circle and text
# @checks:["no_overlap", "formula_readable"]
class DemoScene(Scene):
    def construct(self):
        circle = Circle(radius=2, color=BLUE)
        text = MathTex(r"x^2 + y^2 = r^2").next_to(circle, DOWN, buff=0.5)

        self.play(Create(circle))
        self.play(Write(text))
        self.wait(2)
```

### 必须包含的注释

| 注释 | 用途 |
|------|------|
| `# @segment:{id}` | 标记 segment 边界 |
| `# @time:{start}-{end}s` | 声明时间范围 |
| `# @keyframes:[...]` | 关键帧时间点 |
| `# @description:...` | 人类可读描述 |
| `# @checks:[...]` | 声明要运行的检查 |

---

## Phase 5: 静态检查（Layer 1）

```bash
macode check scenes/05_new_scene/
```

读取报告：
```bash
cat .agent/check_reports/05_new_scene_static.json | jq .
```

### 常见 issue 及修复

| Issue 类型 | 含义 | 修复 |
|------------|------|------|
| `duration_mismatch` | 动画时间与 manifest 不符 | 调整 `self.wait()` 或 `run_time=` |
| `buff_missing` | `next_to()` 缺少 `buff` | 添加 `buff=0.5` |
| `possible_overflow` | 坐标超出画布 | 调整 `move_to()` / `shift()` |
| `extreme_scale` | `scale()` 值异常 | 调整到 0.3–3.0 范围 |
| `segment_mismatch` | manifest segment 与 source 不匹配 | 检查 `@segment:` 注释 |

---

## Phase 6: 渲染

```bash
macode render scenes/05_new_scene/
```

如果失败，查看日志：
```bash
ls -lt .agent/log/ | head -5
tail -50 .agent/log/20260510_xxxxxx_05_new_scene.log
```

---

## Phase 7: 帧检查（Layer 2）

```bash
macode check scenes/05_new_scene/ --frames
```

读取报告：
```bash
cat .agent/check_reports/05_new_scene_frames.json | jq .
```

### 常见 issue

| Issue 类型 | 含义 | 修复 |
|------------|------|------|
| `overlap` | 元素重叠 | 调整位置间距 |
| `low_contrast` | 公式对比度不足 | 调整颜色或背景 |
| `out_of_focus` | 相机未聚焦 | 添加 `self.camera.frame` 动画 |

---

## Phase 8: 迭代修复

如果 Layer 1 或 Layer 2 发现问题：

1. 读取 check report 中的 `fix` 块
2. 判断 `fix_confidence`：
   - `>= 0.8` → 按 `fix.params` 自动修改
   - `< 0.8` → 请求人类确认（记录问题并等待人工决策）
3. 修改源码
4. **清除缓存**（重要！修改后必须重新渲染）：
   ```bash
   rm -rf .agent/tmp/05_new_scene/frames/
   ```
5. 重新运行 check → render → check

---

## Phase 9: 提交

```bash
git add scenes/05_new_scene/
git commit -m "agent: add 05_new_scene — [engine] [duration]s"
```

---

## 完整命令流（一键复制）

```bash
# 设置环境
export PATH="$PWD/bin:$PATH"

# 创建场景
mkdir -p scenes/05_new_scene
# （写入 manifest.json 和 scene.py）

# 检查 → 修复 → 渲染 → 再检查
macode check scenes/05_new_scene/
# （读取 .agent/check_reports/05_new_scene_static.json，修复 issue）
macode render scenes/05_new_scene/
macode check scenes/05_new_scene/ --frames
# （读取 .agent/check_reports/05_new_scene_frames.json，修复 issue）

# 提交
git add scenes/05_new_scene/
git commit -m "agent: render 05_new_scene"
```
