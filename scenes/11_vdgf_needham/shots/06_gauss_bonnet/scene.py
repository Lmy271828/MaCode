"""scenes/11_vdgf_needham/shots/06_gauss_bonnet/scene.py
Gauss-Bonnet 定理：局部曲率与全局拓扑的联姻。
"""

from manimlib import *
import numpy as np

BG_COLOR = "#1A1A2E"
GOLD = "#E8D5B7"
BLUE = "#4A90E2"
RED = "#E74C3C"
GREEN = "#2ECC71"
WHITE = "#F0F0F0"

class GaussBonnetScene(Scene):
    def construct(self):
        # Background
        bg = Rectangle(width=20, height=12, fill_color="#1A1A2E", fill_opacity=1, stroke_width=0)
        bg.shift(UP * 0.5)
        self.add(bg)

        title = Text("Gauss-Bonnet 定理 —— 局部与全局的桥梁", font_size=40, color=GOLD)
        title.to_edge(UP, buff=0.4)
        self.play(Write(title, run_time=2.2))
        self.wait(2.0)

        # 核心公式
        formula = Tex(r"\int_M K \, dA = 2\pi \, \chi(M)", font_size=48, color=GOLD)
        formula.move_to(UP * 2)
        self.play(Write(formula, run_time=3.0))
        self.wait(4.0)

        # 三个示例
        # 球面
        sphere_ex = VGroup(
            Circle(radius=0.8, color=RED, stroke_width=2),
            Text("球面", font_size=22, color=RED),
            Tex(r"K = +1", font_size=20, color=RED),
            Tex(r"\chi = 2", font_size=20, color=RED),
            Tex(r"\int K = 4\pi", font_size=20, color=RED),
        )
        sphere_ex.arrange(DOWN, buff=0.15)

        # 环面
        torus_k_text = VGroup(
            Tex(r"K", font_size=20, color=BLUE),
            Text(" 有正有负", font_size=20, color=BLUE),
        )
        torus_k_text.arrange(RIGHT, buff=0.1)
        torus_ex = VGroup(
            self.draw_torus_outline(),
            Text("环面", font_size=22, color=BLUE),
            torus_k_text,
            Tex(r"\chi = 0", font_size=20, color=BLUE),
            Tex(r"\int K = 0", font_size=20, color=BLUE),
        )
        torus_ex.arrange(DOWN, buff=0.15)

        # 双环面
        double_ex = VGroup(
            Text("双环面", font_size=22, color=GREEN),
            Tex(r"\chi = -2", font_size=20, color=GREEN),
            Tex(r"\int K = -4\pi", font_size=20, color=GREEN),
        )
        double_ex.arrange(DOWN, buff=0.15)

        examples = VGroup(sphere_ex, torus_ex, double_ex)
        examples.arrange(RIGHT, buff=2.5)
        examples.move_to(DOWN * 0.3)

        self.play(FadeIn(sphere_ex, run_time=1.8))
        self.wait(2.0)
        self.play(FadeIn(torus_ex, run_time=1.8))
        self.wait(2.0)
        self.play(FadeIn(double_ex, run_time=1.8))
        self.wait(6.0)

        # 欧拉示性数解释
        euler_label = Text("欧拉示性数", font_size=26, color=WHITE)
        euler_label.move_to(DOWN * 2.3)
        self.play(Write(euler_label, run_time=1.5))

        euler_formula = Tex(r"\chi = V - E + F", font_size=28, color=WHITE)
        euler_formula.next_to(euler_label, DOWN, buff=0.3)
        self.play(Write(euler_formula, run_time=1.8))
        self.wait(4.0)

        # 结论
        conclusion = Text("局部几何（曲率）完全决定了全局拓扑（欧拉数）", font_size=26, color=GOLD)
        conclusion.move_to(DOWN * 3.4)
        self.play(Write(conclusion, run_time=2.2))
        self.wait(12.0)

        self.play(FadeOut(VGroup(
            title, formula, sphere_ex, torus_ex, double_ex,
            euler_label, euler_formula, conclusion
        )), run_time=2.2)
        self.wait(2.0)

    def draw_torus_outline(self):
        # 简化的环面轮廓
        outer = Circle(radius=0.9, color=BLUE, stroke_width=2)
        inner = Circle(radius=0.4, color=BLUE, stroke_width=2)
        inner.set_fill(BG_COLOR, opacity=1)
        return VGroup(outer, inner)
