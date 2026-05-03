from manim import *


class TitleScene(Scene):
    """Phase 1 标题场景：显示标题文字，持续 2 秒。"""

    def construct(self):
        title = Text("MaCode 演示", font_size=72)
        self.play(Write(title), run_time=2)
