"""scenes/11_vdgf_needham/shots/07_forms/scene.py
微分形式：统一向量微积分的力量。
"""

from manimlib import *

BG_COLOR = "#1A1A2E"
GOLD = "#E8D5B7"
BLUE = "#4A90E2"
RED = "#E74C3C"
GREEN = "#2ECC71"
WHITE = "#F0F0F0"

class DifferentialFormsScene(Scene):
    def construct(self):
        # Background
        bg = Rectangle(width=20, height=12, fill_color="#1A1A2E", fill_opacity=1, stroke_width=0)
        bg.shift(UP * 0.5)
        self.add(bg)

        title = Text("Act V  微分形式 —— 统一的语言", font_size=40, color=GOLD)
        title.to_edge(UP, buff=0.4)
        self.play(Write(title, run_time=2.2))
        self.wait(2.0)

        # 1-形式和 2-形式的几何直观
        form_label = Text("1-形式  →  2-形式", font_size=28, color=WHITE)
        form_label.move_to(UP * 2)
        self.play(Write(form_label, run_time=1.5))

        # 1-形式：一族超平面（用平行线表示）
        one_form = VGroup()
        for i in range(-3, 4):
            line = Line(LEFT * 2 + UP * i * 0.4, RIGHT * 2 + UP * i * 0.4, color=BLUE, stroke_width=1.5)
            one_form.add(line)
        one_form.move_to(LEFT * 3.5)
        one_label = Text("1-形式", font_size=22, color=BLUE).next_to(one_form, DOWN, buff=0.3)
        self.play(ShowCreation(one_form, run_time=2.2), Write(one_label, run_time=1.2))

        # 箭头：外微分 d
        d_arrow = Arrow(LEFT * 1.2, RIGHT * 1.2, color=GOLD, buff=0.1)
        d_label = Tex(r"d", font_size=36, color=GOLD).next_to(d_arrow, UP, buff=0.1)
        self.play(ShowCreation(d_arrow, run_time=1.2), Write(d_label, run_time=1.2))

        # 2-形式：有向面积元（用网格表示）
        two_form = VGroup()
        for i in range(-3, 4):
            for j in range(-2, 3):
                rect = Rectangle(height=0.35, width=0.35, stroke_color=GREEN, stroke_width=1)
                rect.move_to(RIGHT * 3.5 + UP * i * 0.4 + RIGHT * j * 0.4)
                two_form.add(rect)
        two_label = Text("2-形式", font_size=22, color=GREEN).next_to(two_form, DOWN, buff=0.3)
        self.play(FadeIn(two_form, run_time=1.8), Write(two_label, run_time=1.2))

        self.wait(4.0)

        # 统一公式
        stokes = Tex(r"\int_{\Omega} d\omega = \int_{\partial \Omega} \omega", font_size=40, color=GOLD)
        stokes.move_to(DOWN * 1.5)
        self.play(Write(stokes, run_time=3.0))
        self.wait(6.0)

        # 统一了哪些定理
        unify = VGroup(
            Text("•  格林定理", font_size=22, color=WHITE),
            Text("•  斯托克斯定理", font_size=22, color=WHITE),
            Text("•  高斯散度定理", font_size=22, color=WHITE),
        )
        unify.arrange(DOWN, buff=0.2, aligned_edge=LEFT)
        unify.move_to(DOWN * 3.0)
        self.play(FadeIn(unify, run_time=2.2))
        self.wait(8.0)

        # 麦克斯韦方程组
        maxwell_title = Text("麦克斯韦方程组的简洁形式", font_size=24, color=BLUE)
        maxwell_title.next_to(unify, DOWN, buff=0.4)
        self.play(Write(maxwell_title, run_time=1.5))

        maxwell = VGroup(
            Tex(r"d\mathbf{F} = 0", font_size=26, color=BLUE),
            Tex(r"d{\star}\mathbf{F} = \mathbf{J}", font_size=26, color=BLUE),
        )
        maxwell.arrange(RIGHT, buff=1.5)
        maxwell.next_to(maxwell_title, DOWN, buff=0.3)
        self.play(FadeIn(maxwell, run_time=1.8))
        self.wait(10.0)

        self.play(FadeOut(VGroup(
            title, form_label, one_form, one_label, d_arrow, d_label,
            two_form, two_label, stokes, unify, maxwell_title, maxwell
        )), run_time=2.2)
        self.wait(2.0)
