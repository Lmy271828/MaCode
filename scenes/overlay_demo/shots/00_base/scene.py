"""Overlay Demo — Base Segment (ManimGL)

Blue gradient background with grid pattern.
"""

from manimlib import *
from templates.scene_base import MaCodeScene


class BaseScene(MaCodeScene):
    def construct(self):
        self.camera.background_rgb = [0.02, 0.05, 0.15]

        # Grid background
        grid = NumberPlane(
            x_range=[-10, 10, 1],
            y_range=[-6, 6, 1],
            background_line_style={
                "stroke_color": BLUE_E,
                "stroke_width": 1,
                "stroke_opacity": 0.3,
            },
        )
        self.play(ShowCreation(grid), run_time=1.0)

        # Large blue circle
        circle = Circle(radius=2.5, color=BLUE_C)
        circle.set_fill(BLUE_D, opacity=0.4)
        circle.set_stroke(BLUE_B, width=3)
        self.play(ShowCreation(circle), run_time=1.0)

        label = Text("Base Layer", font_size=36, color=BLUE_A)
        label.to_edge(UP, buff=0.5)
        self.play(FadeIn(label), run_time=0.5)

        self.wait(1.0)
        self.play(FadeOut(grid), FadeOut(circle), FadeOut(label), run_time=0.5)
