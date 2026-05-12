"""scenes/06_ffmpeg_demo/scene.py
FFmpeg Builder 演示场景。

场景本身是一个简单的几何动画，重点在于配套的
``test_ffmpeg_builder.py`` 验证 ffmpeg_builder 的命令生成能力。
"""

from manim import *


class FFMpegDemoScene(Scene):
    """ffmpeg_builder 演示场景：简单的圆动画。"""

    def construct(self):
        circle = Circle(radius=2, color=BLUE)
        self.play(Create(circle), run_time=1.5)
        self.play(FadeOut(circle), run_time=1.0)
