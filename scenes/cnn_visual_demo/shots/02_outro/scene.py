"""CNN Visual Demo — Outro Segment

Summary and branding.
"""

from manimlib import *
from templates.scene_base import MaCodeScene


class OutroScene(MaCodeScene):
    def construct(self):
        self.camera.background_rgb = [0.05, 0.05, 0.08]

        summary = Text("卷积提取特征 · 神经网络学习表示", font_size=32, color=GREY_B)
        summary.to_edge(UP, buff=1.0)

        brand = Text("Rendered with MaCode", font_size=24, color=BLUE_D)
        brand.next_to(summary, DOWN, buff=0.6)

        self.play(FadeIn(summary), run_time=0.5)
        self.wait(0.3)
        self.play(FadeIn(brand), run_time=0.5)
        self.wait(0.5)
        self.play(FadeOut(summary), FadeOut(brand), run_time=0.3)
