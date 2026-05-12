"""CNN Visual Demo — Main Segment

Convolution operation visualization:
- 5x5 input grid (grayscale values)
- 3x3 kernel sliding over input
- Output feature map computation
"""

from manimlib import *
from templates.scene_base import MaCodeScene


class MainScene(MaCodeScene):
    def construct(self):
        self.camera.background_rgb = [0.05, 0.05, 0.08]

        # Input grid: 5x5, values 0-9
        input_values = [
            [1, 2, 3, 0, 1],
            [4, 5, 6, 1, 2],
            [7, 8, 9, 2, 3],
            [0, 1, 2, 3, 4],
            [1, 0, 1, 2, 1],
        ]

        # Kernel: 3x3 edge detector
        kernel_values = [
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0],
        ]

        cell_size = 0.5
        grid_group = VGroup()
        input_cells = {}

        # Build input grid
        for i, row in enumerate(input_values):
            for j, val in enumerate(row):
                color = interpolate_color(BLACK, WHITE, val / 9)
                cell = Square(side_length=cell_size)
                cell.set_fill(color, opacity=0.9)
                cell.set_stroke(GREY_D, width=1)
                cell.move_to(
                    LEFT * 2 + UP * 1.5
                    + RIGHT * j * cell_size
                    + DOWN * i * cell_size
                )
                label = Text(str(val), font_size=16, color=WHITE)
                label.move_to(cell.get_center())
                grid_group.add(cell, label)
                input_cells[(i, j)] = (cell, label)

        # Input label
        input_label = Text("输入图像 (5×5)", font_size=20, color=GREY_B)
        input_label.next_to(grid_group, DOWN, buff=0.3)

        # Kernel grid
        kernel_group = VGroup()
        for i, row in enumerate(kernel_values):
            for j, val in enumerate(row):
                color = RED if val < 0 else (GREEN if val > 0 else GREY)
                cell = Square(side_length=cell_size)
                cell.set_fill(color, opacity=0.3)
                cell.set_stroke(color, width=2)
                cell.move_to(
                    RIGHT * 3.5 + UP * 1.5
                    + RIGHT * j * cell_size
                    + DOWN * i * cell_size
                )
                label = Text(str(val), font_size=16, color=WHITE)
                label.move_to(cell.get_center())
                kernel_group.add(cell, label)

        kernel_label = Text("卷积核 (3×3)", font_size=20, color=GREY_B)
        kernel_label.next_to(kernel_group, DOWN, buff=0.3)

        # Output grid: 3x3
        output_values = [
            [21, 18, 9],
            [24, 21, 18],
            [15, 18, 15],
        ]
        output_group = VGroup()
        for i, row in enumerate(output_values):
            for j, val in enumerate(row):
                color = interpolate_color(BLACK, BLUE, val / 30)
                cell = Square(side_length=cell_size)
                cell.set_fill(color, opacity=0.9)
                cell.set_stroke(GREY_D, width=1)
                cell.move_to(
                    RIGHT * 0.5 + DOWN * 2.5
                    + RIGHT * j * cell_size
                    + DOWN * i * cell_size
                )
                label = Text(str(val), font_size=16, color=WHITE)
                label.move_to(cell.get_center())
                output_group.add(cell, label)

        output_label = Text("特征图 (3×3)", font_size=20, color=GREY_B)
        output_label.next_to(output_group, DOWN, buff=0.3)

        # Arrow
        arrow = Arrow(
            kernel_group.get_bottom() + DOWN * 0.2,
            output_group.get_top() + UP * 0.2,
            color=BLUE_C,
            buff=0.1,
        )
        conv_text = Text("卷积运算", font_size=18, color=BLUE_C)
        conv_text.next_to(arrow, RIGHT, buff=0.1)

        # Animate
        self.play(FadeIn(grid_group), FadeIn(input_label), run_time=0.5)
        self.wait(0.3)
        self.play(FadeIn(kernel_group), FadeIn(kernel_label), run_time=0.5)
        self.wait(0.3)

        # Sliding kernel highlight
        highlight = Square(side_length=cell_size * 3)
        highlight.set_stroke(YELLOW, width=3)
        highlight.set_fill(YELLOW, opacity=0.1)
        highlight.move_to(input_cells[(0, 0)][0].get_center() + RIGHT * cell_size + DOWN * cell_size)

        self.play(ShowCreation(highlight), run_time=0.3)

        # Slide to next positions
        for pos in [(0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2)]:
            i, j = pos
            target = (
                input_cells[(i, j)][0].get_center()
                + RIGHT * cell_size
                + DOWN * cell_size
            )
            self.play(highlight.animate.move_to(target), run_time=0.25)

        self.play(FadeOut(highlight), run_time=0.2)
        self.wait(0.2)

        # Show output
        self.play(
            FadeIn(arrow), FadeIn(conv_text),
            FadeIn(output_group), FadeIn(output_label),
            run_time=0.5,
        )
        self.wait(1.0)

        # Fade out all
        self.play(
            FadeOut(grid_group), FadeOut(input_label),
            FadeOut(kernel_group), FadeOut(kernel_label),
            FadeOut(output_group), FadeOut(output_label),
            FadeOut(arrow), FadeOut(conv_text),
            run_time=0.5,
        )
