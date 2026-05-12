"""CNN Visual Demo — Activation Segment (25s)

ReLU: f(x) = max(0, x)
"""

from manimlib import *
from templates.scene_base import MaCodeScene


class ActivationScene(MaCodeScene):
    def construct(self):
        self.camera.background_rgb = [0.05, 0.05, 0.08]

        title = Text("激活函数: ReLU", font_size=32, color=GREY_B)
        title.to_edge(UP, buff=0.5)
        self.play(FadeIn(title), run_time=0.5)

        # Axes
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-1, 3, 1],
            axis_config={"stroke_color": GREY_B, "stroke_width": 2},
            height=3.5,
            width=5,
        )
        axes.move_to(DOWN * 0.3)

        relu_graph = axes.get_graph(lambda x: max(0, x), color=GREEN, x_range=[-3, 3])
        relu_label = Text("f(x)=max(0,x)", font_size=20, color=GREEN)
        relu_label.next_to(axes.get_top(), RIGHT, buff=0.2)

        self.play(ShowCreation(axes), run_time=0.5)
        self.play(ShowCreation(relu_graph), FadeIn(relu_label), run_time=0.8)
        self.wait(0.5)

        # Highlight negative region suppression
        neg_region = Rectangle(height=2.5, width=2.8, color=RED, fill_opacity=0.1)
        neg_region.move_to(axes.c2p(-1.5, 1))
        neg_label = Text("负值 → 0", font_size=18, color=RED)
        neg_label.next_to(neg_region, LEFT, buff=0.2)

        self.play(FadeIn(neg_region), FadeIn(neg_label), run_time=0.5)
        self.wait(0.5)

        # Grid before/after
        cell_size = 0.4
        before_group = VGroup()
        before_vals = [-1, 2, -0.5, 3, -2, 1]
        for i, v in enumerate(before_vals):
            sq = Square(side_length=cell_size)
            sq.set_fill(WHITE if v > 0 else GREY_E, opacity=abs(v) / 3)
            sq.set_stroke(GREY_D, width=1)
            sq.move_to(LEFT * 4 + UP * 0.5 + DOWN * (i % 3) * cell_size + RIGHT * (i // 3) * cell_size)
            before_group.add(sq)

        before_label = Text("Before", font_size=16, color=GREY_B)
        before_label.next_to(before_group, DOWN, buff=0.2)

        after_group = VGroup()
        after_vals = [0, 2, 0, 3, 0, 1]
        for i, v in enumerate(after_vals):
            sq = Square(side_length=cell_size)
            sq.set_fill(GREEN if v > 0 else GREY_E, opacity=abs(v) / 3)
            sq.set_stroke(GREY_D, width=1)
            sq.move_to(RIGHT * 3 + UP * 0.5 + DOWN * (i % 3) * cell_size + RIGHT * (i // 3) * cell_size)
            after_group.add(sq)

        after_label = Text("After ReLU", font_size=16, color=GREEN)
        after_label.next_to(after_group, DOWN, buff=0.2)

        arr = Arrow(before_group.get_right(), after_group.get_left(), color=BLUE_C, buff=0.3)

        self.play(FadeIn(before_group), FadeIn(before_label), run_time=0.3)
        self.play(GrowArrow(arr), run_time=0.3)
        self.play(FadeIn(after_group), FadeIn(after_label), run_time=0.3)
        self.wait(1.0)

        self.play(
            FadeOut(title), FadeOut(axes), FadeOut(relu_graph), FadeOut(relu_label),
            FadeOut(neg_region), FadeOut(neg_label),
            FadeOut(before_group), FadeOut(before_label), FadeOut(arr),
            FadeOut(after_group), FadeOut(after_label), run_time=0.5,
        )
