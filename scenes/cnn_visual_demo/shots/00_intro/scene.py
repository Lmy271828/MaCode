"""CNN Visual Demo — Intro Segment (10s)"""

from manimlib import *
from templates.scene_base import MaCodeScene


class IntroScene(MaCodeScene):
    def construct(self):
        self.camera.background_rgb = [0.05, 0.05, 0.08]

        title = Text("CNN 卷积神经网络", font_size=64, color=BLUE_C)
        title.to_edge(UP, buff=0.8)

        subtitle = Text("视觉处理原理演示", font_size=36, color=GREY_B)
        subtitle.next_to(title, DOWN, buff=0.4)

        line = Line(LEFT * 4, RIGHT * 4, color=BLUE_D, stroke_width=2)
        line.next_to(subtitle, DOWN, buff=0.3)

        self.play(FadeIn(title, shift=UP * 0.3), run_time=1.0)
        self.wait(0.3)
        self.play(FadeIn(subtitle, shift=UP * 0.2), run_time=0.8)
        self.play(ShowCreation(line), run_time=0.5)
        self.wait(0.4)
        self.play(FadeOut(title), FadeOut(subtitle), FadeOut(line), run_time=0.5)
