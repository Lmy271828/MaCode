"""Intro segment of composite demo."""

from manim import *
from templates.scene_base import MaCodeScene


class IntroScene(MaCodeScene):
    def construct(self):
        title = Text("Composite Demo", font_size=48)
        title.to_edge(UP)
        self.play(FadeIn(title), run_time=0.8)
        self.wait(0.3)
