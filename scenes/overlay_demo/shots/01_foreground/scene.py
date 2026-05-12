"""Overlay Demo — Foreground Segment (ManimGL)

Red circle + text, positioned for overlay onto base.
"""

from manimlib import *
from templates.scene_base import MaCodeScene


class ForegroundScene(MaCodeScene):
    def construct(self):
        # Transparent-ish background (dark so blend works)
        self.camera.background_rgb = [0.0, 0.0, 0.0]

        # Red circle
        circle = Circle(radius=1.2, color=RED)
        circle.set_fill(RED_D, opacity=0.7)
        circle.set_stroke(RED_B, width=2)
        self.play(ShowCreation(circle), run_time=0.8)

        # Text
        label = Text("Overlay", font_size=32, color=WHITE)
        label.next_to(circle, DOWN, buff=0.3)
        self.play(FadeIn(label), run_time=0.5)

        self.wait(1.2)
        self.play(FadeOut(circle), FadeOut(label), run_time=0.5)
