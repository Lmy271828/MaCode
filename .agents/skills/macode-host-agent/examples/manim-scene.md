# Manim 场景编写示例

## 基础场景

```python
from manim import *

# @segment:intro
# @time:0.0-3.0s
# @keyframes:[0.0, 1.5, 3.0]
# @description:Circle creation with label
# @checks:["no_overlap", "formula_readable"]
class IntroScene(Scene):
    def construct(self):
        circle = Circle(radius=2, color=BLUE)
        label = MathTex(r"x^2 + y^2 = r^2").next_to(circle, DOWN, buff=0.5)

        self.play(Create(circle))
        self.play(Write(label))
        self.wait(1)
```

## 多 Segment 场景

```python
from manim import *

# @segment:proof
# @time:0.0-5.0s
class ProofScene(Scene):
    def construct(self):
        # Step 1: Draw triangle
        triangle = Polygon(LEFT, RIGHT, UP, color=WHITE)
        self.play(Create(triangle))
        self.wait(0.5)

        # Step 2: Label vertices
        a_label = MathTex("A").next_to(UP, UP, buff=0.2)
        b_label = MathTex("B").next_to(LEFT, LEFT, buff=0.2)
        c_label = MathTex("C").next_to(RIGHT, RIGHT, buff=0.2)
        self.play(Write(a_label), Write(b_label), Write(c_label))
        self.wait(0.5)

        # Step 3: Show formula
        formula = MathTex(r"a^2 + b^2 = c^2").to_edge(DOWN)
        self.play(Write(formula))
        self.wait(1)
```

## 布局安全模式

```python
# ✅ 正确：使用 buff
text.next_to(circle, DOWN, buff=0.5)

# ❌ 错误：缺少 buff
text.next_to(circle, DOWN)

# ✅ 正确：坐标在画布内（1920x1080 → 范围约 ±540/±960）
circle.move_to([3, 2, 0])

# ❌ 错误：坐标过于极端
circle.move_to([20, 20, 0])

# ✅ 正确：scale 在合理范围
text.scale(1.2)

# ❌ 错误：极端 scale
text.scale(10)
```

## 时长匹配检查

```python
# manifest.json 声明 duration: 3.0s
# 动画时间计算：
#   Create(circle) 默认 1.0s
#   Write(label) 默认 1.0s
#   wait(1) = 1.0s
#   总计: 3.0s ✅ 匹配

# 如果时间过长：
#   self.wait(5)  # 总计 7.0s ❌ 触发 duration_mismatch
```

## 检查注释规范

```python
# @segment:{id}           ← 必须，标识 segment
# @time:{start}-{end}s    ← 必须，声明时间范围
# @keyframes:[...]        ← 可选，关键帧时间点
# @description:...         ← 可选，人类可读描述
# @checks:[...]            ← 可选，声明要运行的检查
```
