"""scenes/04_base_demo_intro/scene.py
Composite PoC：Intro 片段。

验证点：
1. 作为独立 Scene 可渲染
2. 拼接后成为完整 Act 的一部分
"""

from manim import *
from templates.scene_base import MaCodeScene


class IntroScene(MaCodeScene):
    def construct(self):
        title = Text("MaCodeScene 基类演示", font_size=48)
        title.to_edge(UP)
        self.play(FadeIn(title), run_time=0.8)
        self.wait(0.3)
