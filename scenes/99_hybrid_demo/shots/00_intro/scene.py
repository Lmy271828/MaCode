from manim import *


class HybridIntroScene(Scene):
    """Hybrid Demo: Manim 开场，画一个蓝圆。"""

    def construct(self):
        circle = Circle(radius=2, color=BLUE, fill_opacity=0.5)
        self.play(Create(circle), run_time=2)
        self.wait(0.5)
