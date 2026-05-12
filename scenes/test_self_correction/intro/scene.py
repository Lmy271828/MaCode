"""scenes/test_self_correction/intro/scene.py
Intro segment — Pythagorean theorem title.

This segment is layout-correct (no B1/B2/B3 errors).
"""
from manim import *
from templates.scene_base import MaCodeScene


class IntroScene(MaCodeScene):
    # @segment:intro
    # @time:0.0-2.5s
    # @keyframes:[0.0, 1.5, 2.5]
    # @description:Pythagorean theorem title card
    def construct(self):
        title = Text("Pythagorean Theorem", font_size=64)
        title.to_edge(UP, buff=1.0)

        formula = MathTex("a^2 + b^2 = c^2", font_size=72)
        formula.next_to(title, DOWN, buff=0.8)

        self.play(FadeIn(title), run_time=1.0)
        self.wait(0.5)
        self.play(FadeIn(formula), run_time=1.0)
