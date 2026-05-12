"""scenes/04_base_demo_outro/scene.py
Composite PoC：Outro 片段。

注意：作为独立 Scene，需要重新创建对象再淡出，
这会导致视觉上的"状态不连续"——正是 PoC 要验证的问题。
"""

from manim import *
from templates.scene_base import MaCodeScene


class OutroScene(MaCodeScene):
    def construct(self):
        # 独立 Scene 需要重新创建对象
        title = Text("MaCodeScene 基类演示", font_size=48)
        title.to_edge(UP)
        circle = Circle(radius=1, color=BLUE, fill_opacity=0.7)
        square = Square(side_length=2, color=GREEN, fill_opacity=0.7)
        triangle = Triangle(color=RED, fill_opacity=0.7).scale(1.5)
        circle.move_to(LEFT * 4)
        square.move_to(ORIGIN)
        triangle.move_to(RIGHT * 4)

        self.add(title, circle, square, triangle)
        self.play(FadeOut(*self.mobjects), run_time=0.8)
