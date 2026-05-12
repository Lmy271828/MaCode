"""Main segment of composite demo."""

from manim import *
from templates.scene_base import MaCodeScene


class MainScene(MaCodeScene):
    def construct(self):
        circle = Circle(radius=1, color=BLUE, fill_opacity=0.7)
        square = Square(side_length=2, color=GREEN, fill_opacity=0.7)
        triangle = Triangle(color=RED, fill_opacity=0.7).scale(1.5)

        circle.move_to(LEFT * 4)
        square.move_to(ORIGIN)
        triangle.move_to(RIGHT * 4)

        self.play(
            Create(circle),
            Create(square),
            Create(triangle),
            run_time=1.5,
        )
        self.wait(0.5)

        self.focus_on(circle, zoom=0.8, run_time=1.0)
        self.wait(0.5)

        self.focus_on(triangle, zoom=0.8, run_time=1.0)
        self.wait(0.5)

        self.zoom_to_fit([circle, square, triangle], margin=1.0, run_time=1.5)
        self.wait(0.5)
