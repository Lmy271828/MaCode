"""scenes/05_latex_demo/scene.py
LaTeX 辅助工具演示场景。

验证点：
1. ChineseMathTex — 中文公式渲染
2. Math 链式构建器 — 颜色、缩放、位置
3. cases / matrix / align_eqns / integral / derivative — 常见数学结构
4. precompile_formulas — 批量预编译
"""

from manim import *
from utils.latex_helper import (
    ChineseMathTex,
    math,
    cases,
    matrix,
    align_eqns,
    integral,
    derivative,
    precompile_formulas,
)


class LatexDemoScene(Scene):
    def construct(self):
        # ── 1. 中文公式 ──
        title = ChineseMathTex(r"\text{LaTeX 辅助工具演示}")
        title.to_edge(UP)
        self.play(Write(title), run_time=1)
        self.wait(0.3)

        # ── 2. Math 链式构建器 ──
        eq1 = math("E = mc^2", color=RED, scale=1.3)
        eq1.next_to(title, DOWN, buff=0.8)
        self.play(Write(eq1), run_time=1)
        self.wait(0.3)

        # ── 3. 分段函数 ──
        f_cases = cases(
            ("x^2", "x > 0"),
            ("0",   "x \\leq 0"),
        )
        f_cases.next_to(eq1, DOWN, buff=0.6)
        self.play(Write(f_cases), run_time=1)
        self.wait(0.3)

        # ── 4. 矩阵 ──
        m = matrix([[1, 2], [3, 4]], bracket="brackets")
        m.next_to(f_cases, DOWN, buff=0.6)
        self.play(Write(m), run_time=1)
        self.wait(0.3)

        # ── 5. 对齐方程组 ──
        eqs = align_eqns(
            "E &= mc^2",
            "F &= ma",
        )
        eqs.next_to(m, DOWN, buff=0.6)
        self.play(Write(eqs), run_time=1)
        self.wait(0.3)

        # ── 6. 积分 ──
        int_g = integral(r"e^{-x^2}", var="x", lower=r"-\infty", upper=r"\infty")
        int_g.next_to(eqs, DOWN, buff=0.6)
        self.play(Write(int_g), run_time=1)
        self.wait(0.3)

        # ── 7. 导数 ──
        d = derivative("f(x)", var="x", order=2)
        d.next_to(int_g, DOWN, buff=0.6)
        self.play(Write(d), run_time=1)
        self.wait(0.5)

        # ── 8. 批量预编译演示 ──
        formulas = [
            r"\sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6}",
            r"e^{i\pi} + 1 = 0",
            r"\nabla \cdot \bm{E} = \frac{\rho}{\varepsilon_0}",
        ]
        precompiled = precompile_formulas(formulas)

        group = VGroup(*precompiled)
        group.arrange(DOWN, buff=0.4)
        group.next_to(d, DOWN, buff=0.6)
        self.play(LaggedStart(*[Write(m) for m in precompiled], lag_ratio=0.3), run_time=2)
        self.wait(0.5)

        # 结尾淡出
        self.play(FadeOut(*self.mobjects), run_time=0.8)
