from manim import *


class DemoScene(Scene):
    """Phase 1 演示场景：圆变方，持续 4 秒。"""

    def construct(self):
        circle = Circle(radius=2, color=BLUE)
        square = Square(side_length=4, color=GREEN)
        self.play(Create(circle), run_time=1.5)
        self.play(Transform(circle, square), run_time=2)
        self.play(FadeOut(circle), run_time=0.5)
