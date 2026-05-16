"""scenes/11_vdgf_needham/shots/03_geodesic/scene.py
测地线：直线的内蕴推广。
"""

from manimlib import *
import numpy as np

BG_COLOR = "#1A1A2E"
GOLD = "#E8D5B7"
BLUE = "#4A90E2"
RED = "#E74C3C"
GREEN = "#2ECC71"
WHITE = "#F0F0F0"

class GeodesicScene(Scene):
    def construct(self):
        # Background
        bg = Rectangle(width=20, height=12, fill_color="#1A1A2E", fill_opacity=1, stroke_width=0)
        bg.shift(UP * 0.5)
        self.add(bg)
        title = Text("测地线 —— 「最直」的线", font_size=40, color=GOLD)
        title.to_edge(UP, buff=0.4)
        self.play(Write(title, run_time=2.2))
        self.wait(2.0)

        # 平面上的直线
        plane_label = Text("平面", font_size=26, color=BLUE)
        plane_label.move_to(LEFT * 4.5 + UP * 2)
        self.play(Write(plane_label, run_time=1.2))

        plane_rect = Rectangle(height=3.5, width=3.5, stroke_color=BLUE, stroke_width=1.5)
        plane_rect.move_to(LEFT * 4.5)
        self.play(ShowCreation(plane_rect, run_time=1.5))

        line = Arrow(LEFT * 5.8 + DOWN * 1, LEFT * 3.2 + UP * 1, color=GOLD, stroke_width=2, buff=0)
        line_label = Text("直线", font_size=22, color=GOLD).next_to(line, UP, buff=0.15)
        self.play(ShowCreation(line, run_time=1.5), Write(line_label, run_time=1.2))

        # 球面上的大圆
        sphere_label = Text("球面", font_size=26, color=RED)
        sphere_label.move_to(RIGHT * 4.5 + UP * 2)
        self.play(Write(sphere_label, run_time=1.2))

        sphere = Circle(radius=1.6, color=RED, stroke_width=1.5)
        sphere.move_to(RIGHT * 4.5)
        self.play(ShowCreation(sphere, run_time=1.5))

        great_circle = Arc(1.6, PI/6, PI*2/3, color=GOLD, stroke_width=2.5)
        great_circle.move_arc_center_to(RIGHT * 4.5)
        gc_label = Text("大圆（测地线）", font_size=22, color=GOLD).next_to(great_circle, DOWN, buff=0.3)
        self.play(ShowCreation(great_circle, run_time=2.2), Write(gc_label, run_time=1.5))

        self.wait(4.0)

        # 测地线定义
        defn = VGroup(
            Text("测地线 = 局部最短路径", font_size=26, color=WHITE),
            Text("沿路径前进时不左转、不右转", font_size=26, color=WHITE).set_opacity(0.8),
        )
        defn.arrange(DOWN, buff=0.3)
        defn.move_to(DOWN * 2.8)
        self.play(Write(defn[0], run_time=1.8))
        self.wait(2.0)
        self.play(Write(defn[1], run_time=1.8))
        self.wait(6.0)

        # 航海示例
        example = Text("伦敦 → 纽约 的最短航线不是直线，而是大圆弧", font_size=24, color=BLUE)
        example.next_to(defn, DOWN, buff=0.4)
        self.play(FadeIn(example, run_time=1.5))
        self.wait(10.0)

        self.play(FadeOut(VGroup(
            title, plane_label, plane_rect, line, line_label,
            sphere_label, sphere, great_circle, gc_label,
            defn, example
        )), run_time=2.2)
        self.wait(2.0)
