"""CNN Visual Demo — Input Segment (35s)

Image as pixel matrices. RGB channels.
"""

from manimlib import *
from templates.scene_base import MaCodeScene


class InputScene(MaCodeScene):
    def construct(self):
        self.camera.background_rgb = [0.05, 0.05, 0.08]

        title = Text("输入表示: 像素矩阵", font_size=32, color=GREY_B)
        title.to_edge(UP, buff=0.5)
        self.play(FadeIn(title), run_time=0.5)

        # Grayscale 4x4 grid
        cell_size = 0.5
        gray_group = VGroup()
        gray_vals = [
            [0.1, 0.3, 0.5, 0.7],
            [0.2, 0.4, 0.6, 0.8],
            [0.3, 0.5, 0.7, 0.9],
            [0.4, 0.6, 0.8, 1.0],
        ]
        for i, row in enumerate(gray_vals):
            for j, v in enumerate(row):
                sq = Square(side_length=cell_size)
                sq.set_fill(interpolate_color(BLACK, WHITE, v), opacity=0.9)
                sq.set_stroke(GREY_D, width=1)
                sq.move_to(LEFT * 2 + UP * 1 + RIGHT * j * cell_size + DOWN * i * cell_size)
                gray_group.add(sq)

        gray_label = Text("灰度 (H×W)", font_size=18, color=GREY_B)
        gray_label.next_to(gray_group, DOWN, buff=0.3)

        self.play(FadeIn(gray_group), FadeIn(gray_label), run_time=0.5)
        self.wait(0.5)

        # RGB channels
        colors = [RED, GREEN, BLUE]
        color_labels = ["R", "G", "B"]
        rgb_group = VGroup()
        for c_idx, (color, clabel) in enumerate(zip(colors, color_labels)):
            ch_group = VGroup()
            for i in range(3):
                for j in range(3):
                    sq = Square(side_length=cell_size * 0.7)
                    sq.set_fill(color, opacity=gray_vals[i][j] * 0.8)
                    sq.set_stroke(GREY_D, width=1)
                    sq.move_to(
                        RIGHT * 2.5 + UP * 0.5
                        + RIGHT * j * cell_size * 0.75
                        + DOWN * i * cell_size * 0.75
                        + UP * (1 - c_idx) * 1.8
                    )
                    ch_group.add(sq)
            ch_label = Text(clabel, font_size=16, color=color)
            ch_label.next_to(ch_group, LEFT, buff=0.2)
            rgb_group.add(ch_group, ch_label)

        rgb_title = Text("RGB (H×W×3)", font_size=18, color=GREY_B)
        rgb_title.next_to(rgb_group, DOWN, buff=0.3)

        arrow = Arrow(gray_group.get_right(), rgb_group.get_left(), color=BLUE_C, buff=0.3)
        channel_text = Text("3 通道", font_size=16, color=BLUE_C)
        channel_text.next_to(arrow, UP, buff=0.1)

        self.play(GrowArrow(arrow), FadeIn(channel_text), run_time=0.5)
        self.play(FadeIn(rgb_group), FadeIn(rgb_title), run_time=0.5)
        self.wait(1.0)

        self.play(
            FadeOut(title), FadeOut(gray_group), FadeOut(gray_label),
            FadeOut(arrow), FadeOut(channel_text),
            FadeOut(rgb_group), FadeOut(rgb_title), run_time=0.5,
        )
