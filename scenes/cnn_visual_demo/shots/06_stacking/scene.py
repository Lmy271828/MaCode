"""CNN Visual Demo — Stacking Segment (30s)

Multiple conv + pool layers stacked for hierarchical feature extraction.
"""

from manimlib import *
from templates.scene_base import MaCodeScene


class StackingScene(MaCodeScene):
    def construct(self):
        self.camera.background_rgb = [0.05, 0.05, 0.08]

        title = Text("多层堆叠: 层次化特征提取", font_size=32, color=GREY_B)
        title.to_edge(UP, buff=0.5)
        self.play(FadeIn(title), run_time=0.5)

        # Layer blocks
        layers = [
            ("输入", 224, GREY),
            ("Conv1", 112, BLUE),
            ("Pool1", 56, BLUE_D),
            ("Conv2", 28, GREEN),
            ("Pool2", 14, GREEN_D),
            ("Conv3", 7, YELLOW),
        ]

        layer_group = VGroup()
        for i, (name, size, color) in enumerate(layers):
            rect = Rectangle(height=size / 40, width=0.8)
            rect.set_fill(color, opacity=0.6)
            rect.set_stroke(color, width=2)
            rect.move_to(LEFT * 4 + RIGHT * i * 1.5)
            label = Text(name, font_size=14, color=WHITE)
            label.next_to(rect, DOWN, buff=0.15)
            size_label = Text(f"{size}×{size}", font_size=12, color=GREY_B)
            size_label.next_to(rect, UP, buff=0.1)
            layer_group.add(rect, label, size_label)

            if i > 0:
                arrow = Arrow(
                    layer_group[-6].get_right(), rect.get_left(),
                    color=WHITE, buff=0.1, stroke_width=1,
                )
                layer_group.add(arrow)

        self.play(FadeIn(layer_group), run_time=1.0)
        self.wait(0.5)

        # Feature descriptions
        descs = [
            Text("边缘、纹理", font_size=16, color=BLUE),
            Text("形状、部件", font_size=16, color=GREEN),
            Text("对象、语义", font_size=16, color=YELLOW),
        ]
        for i, desc in enumerate(descs):
            desc.move_to(DOWN * 2 + RIGHT * (i - 1) * 3)
        desc_group = VGroup(*descs)
        self.play(FadeIn(desc_group), run_time=0.5)
        self.wait(1.0)

        self.play(
            FadeOut(title), FadeOut(layer_group), FadeOut(desc_group), run_time=0.5,
        )
