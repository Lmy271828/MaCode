"""Outro segment of composite demo."""

from manim import *
from templates.scene_base import MaCodeScene


class OutroScene(MaCodeScene):
    def construct(self):
        title = Text("Composite Demo", font_size=48)
        title.to_edge(UP)
        circle = Circle(radius=1, color=BLUE, fill_opacity=0.7)
        square = Square(side_length=2, color=GREEN, fill_opacity=0.7)
        triangle = Triangle(color=RED, fill_opacity=0.7).scale(1.5)
        circle.move_to(LEFT * 4)
        square.move_to(ORIGIN)
        triangle.move_to(RIGHT * 4)

        self.add(title, circle, square, triangle)
        self.play(FadeOut(*self.mobjects), run_time=0.8)
