"""CNN Visual Demo — Pooling Segment (35s)

MaxPool 2x2: downsampling by taking max value in each window.
"""

from manimlib import *
from templates.scene_base import MaCodeScene


class PoolingScene(MaCodeScene):
    def construct(self):
        self.camera.background_rgb = [0.05, 0.05, 0.08]

        title = Text("池化层: MaxPool 2×2", font_size=32, color=GREY_B)
        title.to_edge(UP, buff=0.5)
        self.play(FadeIn(title), run_time=0.5)

        # Input 4x4 feature map
        cell_size = 0.5
        input_vals = [
            [1, 3, 2, 1],
            [4, 6, 5, 2],
            [2, 4, 7, 3],
            [1, 2, 3, 1],
        ]
        input_group = VGroup()
        for i, row in enumerate(input_vals):
            for j, v in enumerate(row):
                sq = Square(side_length=cell_size)
                sq.set_fill(interpolate_color(BLACK, BLUE, v / 7), opacity=0.9)
                sq.set_stroke(GREY_D, width=1)
                sq.move_to(LEFT * 2 + UP * 1 + RIGHT * j * cell_size + DOWN * i * cell_size)
                label = Text(str(v), font_size=16, color=WHITE)
                label.move_to(sq.get_center())
                input_group.add(sq, label)

        input_label = Text("特征图 (4×4)", font_size=18, color=GREY_B)
        input_label.next_to(input_group, DOWN, buff=0.3)

        self.play(FadeIn(input_group), FadeIn(input_label), run_time=0.5)
        self.wait(0.3)

        # Highlight 2x2 windows one by one
        windows = [
            (0, 0, 6), (0, 2, 5),
            (2, 0, 4), (2, 2, 7),
        ]
        highlights = VGroup()
        for wi, (si, sj, max_val) in enumerate(windows):
            hl = Square(side_length=cell_size * 2)
            hl.set_stroke(YELLOW, width=3)
            hl.set_fill(YELLOW, opacity=0.1)
            center_i, center_j = si + 0.5, sj + 0.5
            hl.move_to(
                LEFT * 2 + UP * 1
                + RIGHT * center_j * cell_size
                + DOWN * center_i * cell_size
            )
            max_text = Text(f"max={max_val}", font_size=16, color=YELLOW)
            max_text.next_to(hl, UP, buff=0.1)
            highlights.add(hl, max_text)
            self.play(ShowCreation(hl), FadeIn(max_text), run_time=0.4)
            self.wait(0.2)

        # Output 2x2
        output_group = VGroup()
        output_vals = [6, 5, 4, 7]
        for i, v in enumerate(output_vals):
            sq = Square(side_length=cell_size)
            sq.set_fill(interpolate_color(BLACK, BLUE, v / 7), opacity=0.9)
            sq.set_stroke(GREY_D, width=1)
            sq.move_to(RIGHT * 3 + UP * 0.5 + RIGHT * (i % 2) * cell_size + DOWN * (i // 2) * cell_size)
            label = Text(str(v), font_size=16, color=WHITE)
            label.move_to(sq.get_center())
            output_group.add(sq, label)

        output_label = Text("池化后 (2×2)", font_size=18, color=GREY_B)
        output_label.next_to(output_group, DOWN, buff=0.3)

        arr = Arrow(input_group.get_right(), output_group.get_left(), color=BLUE_C, buff=0.3)
        pool_text = Text("2×2 MaxPool", font_size=16, color=BLUE_C)
        pool_text.next_to(arr, UP, buff=0.1)

        self.play(FadeOut(highlights), run_time=0.3)
        self.play(GrowArrow(arr), FadeIn(pool_text), run_time=0.3)
        self.play(FadeIn(output_group), FadeIn(output_label), run_time=0.5)
        self.wait(1.0)

        self.play(
            FadeOut(title), FadeOut(input_group), FadeOut(input_label),
            FadeOut(arr), FadeOut(pool_text),
            FadeOut(output_group), FadeOut(output_label), run_time=0.5,
        )
