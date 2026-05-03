from manim import *


class TestScene(Scene):
    """Phase 0 测试场景：画一个圆，持续 3 秒。"""

    def construct(self):
        circle = Circle(radius=2, color=BLUE)
        self.play(Create(circle), run_time=3)
