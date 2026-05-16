"""scenes/11_vdgf_needham/shots/02_intrinsic/scene.py
内蕴几何：蚂蚁在球面上的寓言，圆周长公式对比。
"""

from manimlib import *
import numpy as np

BG_COLOR = "#1A1A2E"
GOLD = "#E8D5B7"
BLUE = "#4A90E2"
RED = "#E74C3C"
GREEN = "#2ECC71"
WHITE = "#F0F0F0"

class IntrinsicGeometryScene(Scene):
    def construct(self):
        # Background
        bg = Rectangle(width=20, height=12, fill_color="#1A1A2E", fill_opacity=1, stroke_width=0)
        bg.shift(UP * 0.5)
        self.add(bg)

        title = Text("Act II  内蕴 vs 外蕴", font_size=40, color=GOLD)
        title.to_edge(UP, buff=0.4)
        self.play(Write(title, run_time=2.2))
        self.wait(2.0)

        # 左侧：外蕴视角（我们在三维空间看球面）
        extrinsic_label = Text("外蕴视角", font_size=28, color=BLUE)
        extrinsic_label.to_edge(LEFT, buff=1.2).shift(UP * 2.2)
        self.play(Write(extrinsic_label, run_time=1.5))

        sphere_group = VGroup()
        for r in np.linspace(0.4, 1.8, 5):
            c = Circle(radius=r, stroke_color=BLUE, stroke_width=1)
            c.set_stroke(opacity=0.4)
            sphere_group.add(c)
        for angle in np.linspace(0, PI, 5):
            ellipse = Ellipse(width=3.6, height=1.2, stroke_color=BLUE, stroke_width=1)
            ellipse.set_stroke(opacity=0.4)
            ellipse.rotate(angle, axis=OUT)
            sphere_group.add(ellipse)
        sphere_group.shift(LEFT * 3.5 + DOWN * 0.3)
        self.play(ShowCreation(sphere_group, run_time=3.0))

        # 外蕴观察者眼睛
        eye = Dot(radius=0.12, color=WHITE).move_to(LEFT * 6 + UP * 1.5)
        eye_text = Text("我们", font_size=20, color=WHITE).next_to(eye, UP, buff=0.15)
        self.play(FadeIn(eye, run_time=0.8), Write(eye_text, run_time=0.8))

        # 右侧：内蕴视角（蚂蚁在球面上）
        intrinsic_label = Text("内蕴视角", font_size=28, color=RED)
        intrinsic_label.to_edge(RIGHT, buff=1.2).shift(UP * 2.2)
        self.play(Write(intrinsic_label, run_time=1.5))

        # 球面局部放大示意
        local_surface = Circle(radius=1.8, color=RED, stroke_width=2)
        local_surface.shift(RIGHT * 3.5 + DOWN * 0.3)
        self.play(ShowCreation(local_surface, run_time=2.2))

        # 蚂蚁
        ant = Dot(radius=0.1, color=GOLD).move_to(RIGHT * 3.5 + DOWN * 0.3 + UP * 0.5)
        ant_text = Text("二维生物", font_size=20, color=GOLD).next_to(ant, UP, buff=0.2)
        self.play(FadeIn(ant, run_time=0.8), Write(ant_text, run_time=0.8))

        self.wait(4.0)

        # 关键问题
        question = Text("蚂蚁能感知到曲率吗？", font_size=30, color=WHITE)
        question.move_to(DOWN * 2.5)
        self.play(Write(question, run_time=1.8))
        self.wait(6.0)

        # 圆周长对比
        self.play(FadeOut(question, run_time=0.8))

        plane_formula = VGroup(
            Text("平面：", font_size=22, color=BLUE),
            Tex(r"C = 2\pi r", font_size=22, color=BLUE),
        )
        plane_formula.arrange(RIGHT, buff=0.1)
        plane_formula.move_to(LEFT * 3.5 + DOWN * 2.5)

        sphere_formula = VGroup(
            Text("球面：", font_size=22, color=RED),
            Tex(r"C = 2\pi R\sin\frac{r}{R}", font_size=22, color=RED),
        )
        sphere_formula.arrange(RIGHT, buff=0.1)
        sphere_formula.move_to(RIGHT * 3.5 + DOWN * 2.5)

        self.play(Write(plane_formula, run_time=1.8))
        self.wait(2.0)
        self.play(Write(sphere_formula, run_time=2.2))
        self.wait(4.0)

        # 结论
        conclusion = Text("曲率可以被「居住者」感知！", font_size=28, color=GOLD)
        conclusion.move_to(DOWN * 3.2)
        self.play(Write(conclusion, run_time=1.8))
        self.wait(10.0)

        self.play(FadeOut(VGroup(
            title, extrinsic_label, sphere_group, eye, eye_text,
            intrinsic_label, local_surface, ant, ant_text,
            plane_formula, sphere_formula, conclusion
        )), run_time=2.2)
        self.wait(2.0)
