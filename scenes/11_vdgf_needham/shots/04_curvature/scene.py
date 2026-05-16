"""scenes/11_vdgf_needham/shots/04_curvature/scene.py
曲率：高斯曲率的直观理解。
"""

from manimlib import *
import numpy as np

BG_COLOR = "#1A1A2E"
GOLD = "#E8D5B7"
BLUE = "#4A90E2"
RED = "#E74C3C"
GREEN = "#2ECC71"
WHITE = "#F0F0F0"

class CurvatureScene(Scene):
    def construct(self):
        # Background
        bg = Rectangle(width=20, height=12, fill_color="#1A1A2E", fill_opacity=1, stroke_width=0)
        bg.shift(UP * 0.5)
        self.add(bg)
        title = Text("Act III  曲率 —— 空间弯曲的程度", font_size=40, color=GOLD)
        title.to_edge(UP, buff=0.4)
        self.play(Write(title, run_time=2.2))
        self.wait(2.0)

        # 三种局部曲面
        labels = VGroup(
            Text("正曲率", font_size=24, color=RED),
            Text("零曲率", font_size=24, color=BLUE),
            Text("负曲率", font_size=24, color=GREEN))
        labels.arrange(RIGHT, buff=3.5)
        labels.move_to(UP * 2)
        self.play(FadeIn(labels, run_time=1.8))

        # 正曲率：局部球面
        pos_surface = self.draw_paraboloid(RED, +1)
        pos_surface.move_to(LEFT * 4.5)
        self.play(ShowCreation(pos_surface, run_time=2.2))

        # 零曲率：平面
        zero_surface = Square(side_length=2.2, stroke_color=BLUE, stroke_width=1.5)
        zero_surface.move_to(ORIGIN)
        grid = VGroup(*[
            Line(UP * 1.1 + LEFT * 1.1 + RIGHT * i * 0.44, UP * 1.1 + LEFT * 1.1 + RIGHT * i * 0.44 + DOWN * 2.2, color=BLUE, stroke_width=0.8)
            for i in range(6)
        ] + [
            Line(LEFT * 1.1 + UP * 1.1 + DOWN * i * 0.44, LEFT * 1.1 + UP * 1.1 + DOWN * i * 0.44 + RIGHT * 2.2, color=BLUE, stroke_width=0.8)
            for i in range(6)
        ])
        zero_group = VGroup(zero_surface, grid)
        zero_group.move_to(ORIGIN)
        self.play(ShowCreation(zero_surface, run_time=1.5), FadeIn(grid, run_time=1.5))

        # 负曲率：局部马鞍面
        neg_surface = self.draw_paraboloid(GREEN, -1)
        neg_surface.move_to(RIGHT * 4.5)
        self.play(ShowCreation(neg_surface, run_time=2.2))

        self.wait(4.0)

        # 特征对比
        features = VGroup(
            VGroup(
                Tex(r"K > 0", color=RED, font_size=28),
                Tex(r"C < 2\pi r", color=RED, font_size=22),
                Tex(r"\sum \alpha_i > \pi", color=RED, font_size=22)).arrange(DOWN, buff=0.2),
            VGroup(
                Tex(r"K = 0", color=BLUE, font_size=28),
                Tex(r"C = 2\pi r", color=BLUE, font_size=22),
                Tex(r"\sum \alpha_i = \pi", color=BLUE, font_size=22)).arrange(DOWN, buff=0.2),
            VGroup(
                Tex(r"K < 0", color=GREEN, font_size=28),
                Tex(r"C > 2\pi r", color=GREEN, font_size=22),
                Tex(r"\sum \alpha_i < \pi", color=GREEN, font_size=22)).arrange(DOWN, buff=0.2))
        features.arrange(RIGHT, buff=2.2)
        features.move_to(DOWN * 2.6)

        for f in features:
            self.play(FadeIn(f, run_time=1.5), rate_func=smooth)
            self.wait(1.2)

        self.wait(8.0)

        # 高斯曲率公式提示
        k_formula = Tex(r"K = \kappa_1 \cdot \kappa_2", font_size=32, color=GOLD)
        k_formula.move_to(DOWN * 3.5)
        self.play(Write(k_formula, run_time=1.8))
        self.wait(8.0)

        self.play(FadeOut(VGroup(
            title, labels, pos_surface, zero_group, neg_surface,
            features, k_formula
        )), run_time=2.2)
        self.wait(2.0)

    def draw_paraboloid(self, color, sign):
        # 用参数曲线近似局部曲面 z = sign * (x^2 + y^2) 或 z = sign * (x^2 - y^2)
        if sign > 0:
            curves = VGroup()
            for r in np.linspace(0.2, 1.0, 5):
                circle = Circle(radius=r, color=color, stroke_width=1.2)
                circle.set_fill(BG_COLOR, opacity=0)
                circle.scale(1.0)
                curves.add(circle)
            for angle in np.linspace(0, PI, 6):
                pts = []
                for r in np.linspace(0, 1.0, 20):
                    x = r * np.cos(angle)
                    y = r * np.sin(angle)
                    z = sign * (x**2 + y**2) * 0.8
                    pts.append(np.array([x, y, z]))
                line = VMobject(color=color, stroke_width=1.2)
                line.set_points_smoothly([*pts])
                curves.add(line)
            return curves
        else:
            curves = VGroup()
            # 双曲抛物面 z = x^2 - y^2
            for c in np.linspace(-0.8, 0.8, 7):
                pts = []
                for t in np.linspace(-1, 1, 30):
                    x = t
                    y = np.sqrt(max(0, t**2 - c)) if t**2 >= c else np.nan
                    if not np.isnan(y):
                        z = sign * (t**2 - y**2) * 0.8
                        pts.append(np.array([x, y, z]))
                if len(pts) > 1:
                    line = VMobject(color=color, stroke_width=1.2)
                    line.set_points_smoothly(pts)
                    curves.add(line)
                    line2 = VMobject(color=color, stroke_width=1.2)
                    line2.set_points_smoothly([[p[0], -p[1], p[2]] for p in pts])
                    curves.add(line2)
            return curves
