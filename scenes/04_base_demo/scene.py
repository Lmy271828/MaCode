"""scenes/04_base_demo/scene.py
MaCodeScene 基类演示场景。

验证点：
1. 基类自动注入路径（无需 sys.path.insert 即可 import utils）
2. 相机聚焦/缩放便利方法
3. 开场/结尾钩子覆盖
"""

from manim import *
from templates.scene_base import MaCodeScene


class BaseDemoScene(MaCodeScene):
    """演示 MaCodeScene 基类能力的场景。"""

    AUTO_INTRO = True
    AUTO_OUTRO = True

    # @segment:intro
    # @time:0-1.1s
    # @keyframes:[0, 0.8, 1.1]
    # @description:淡入标题作为开场
    # @description:Title segment
    def intro(self):
        """淡入标题作为开场。"""
        title = Text("MaCodeScene 基类演示", font_size=48)
        title.to_edge(UP)
        self.play(FadeIn(title), run_time=0.8)
        self.wait(0.3)

    # @segment:main
    # @time:1.1-6.1s
    # @keyframes:[1.1, 3.1, 4.6, 6.1]
    # @description:创建几何体并测试相机聚焦与缩放
    # @description:Main demonstration
    def construct(self):
        # 创建三个几何体，分散在不同位置
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

        # 测试 focus_on：聚焦到 circle 并放大
        self.focus_on(circle, zoom=0.8, run_time=1.0)
        self.wait(0.5)

        # 测试 focus_on：聚焦到 triangle
        self.focus_on(triangle, zoom=0.8, run_time=1.0)
        self.wait(0.5)

        # 测试 zoom_to_fit：回到全景视角
        self.zoom_to_fit([circle, square, triangle], margin=1.0, run_time=1.5)
        self.wait(0.5)

    # @segment:outro
    # @time:6.1-6.9s
    # @keyframes:[6.1, 6.9]
    # @description:淡出所有元素作为结尾
    # @description:Conclusion
    def outro(self):
        """淡出所有元素作为结尾。"""
        self.play(FadeOut(*self.mobjects), run_time=0.8)
