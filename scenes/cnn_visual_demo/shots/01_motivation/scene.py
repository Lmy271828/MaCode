"""CNN Visual Demo — Motivation Segment (30s)

Why CNN? Traditional fully-connected layer parameter explosion.
"""

from manimlib import *
from templates.scene_base import MaCodeScene


class MotivationScene(MaCodeScene):
    def construct(self):
        self.camera.background_rgb = [0.05, 0.05, 0.08]

        title = Text("传统全连接层的问题", font_size=32, color=GREY_B)
        title.to_edge(UP, buff=0.5)
        self.play(FadeIn(title), run_time=0.5)

        # Input image representation
        img = Square(side_length=2.0)
        img.set_fill(GREY_C, opacity=0.3)
        img.set_stroke(WHITE, width=2)
        img.move_to(LEFT * 3.5)
        img_label = Text("224×224 图像", font_size=18, color=GREY_B)
        img_label.next_to(img, DOWN, buff=0.2)

        self.play(FadeIn(img), FadeIn(img_label), run_time=0.5)
        self.wait(0.3)

        # Fully connected neuron
        neuron = Circle(radius=0.3, color=RED)
        neuron.move_to(RIGHT * 2)
        neuron_label = Text("1 个神经元", font_size=18, color=GREY_B)
        neuron_label.next_to(neuron, DOWN, buff=0.2)

        arrow = Arrow(img.get_right(), neuron.get_left(), color=YELLOW, buff=0.3)
        param_text = Text("50,176 个参数", font_size=20, color=YELLOW)
        param_text.next_to(arrow, UP, buff=0.1)

        self.play(GrowArrow(arrow), run_time=0.5)
        self.play(FadeIn(param_text), FadeIn(neuron), FadeIn(neuron_label), run_time=0.5)
        self.wait(0.5)

        # Many neurons
        many = VGroup(*[Circle(radius=0.15, color=RED, stroke_width=1) for _ in range(20)])
        many.arrange_in_grid(n_rows=4, n_cols=5, buff=0.15)
        many.move_to(RIGHT * 2.5)
        many_label = Text("1000 个神经元 → 5000万+ 参数", font_size=20, color=RED)
        many_label.next_to(many, DOWN, buff=0.3)

        self.play(FadeOut(neuron), FadeOut(neuron_label), FadeOut(param_text), run_time=0.3)
        self.play(FadeIn(many), FadeIn(many_label), run_time=0.5)
        self.wait(0.5)

        # CNN solution
        cnn_text = Text("卷积神经网络: 局部连接 + 权值共享", font_size=24, color=GREEN)
        cnn_text.to_edge(DOWN, buff=0.5)
        self.play(FadeIn(cnn_text), run_time=0.5)
        self.wait(1.0)

        self.play(
            FadeOut(title), FadeOut(img), FadeOut(img_label),
            FadeOut(arrow), FadeOut(many), FadeOut(many_label),
            FadeOut(cnn_text), run_time=0.5,
        )
