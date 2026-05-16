"""scenes/11_vdgf_needham/shots/05_theorema/scene.py
高斯绝妙定理：曲率是内蕴的。
"""

from manimlib import *

BG_COLOR = "#1A1A2E"
GOLD = "#E8D5B7"
BLUE = "#4A90E2"
RED = "#E74C3C"
GREEN = "#2ECC71"
WHITE = "#F0F0F0"

class TheoremaEgregiumScene(Scene):
    def construct(self):
        # Background
        bg = Rectangle(width=20, height=12, fill_color="#1A1A2E", fill_opacity=1, stroke_width=0)
        bg.shift(UP * 0.5)
        self.add(bg)

        title = Text("Theorema Egregium —— 高斯绝妙定理", font_size=40, color=GOLD)
        title.to_edge(UP, buff=0.4)
        self.play(Write(title, run_time=2.2))
        self.wait(2.0)

        # 左侧：圆柱面可以被展平
        cyl_label = Text("圆柱面  K = 0", font_size=26, color=BLUE)
        cyl_label.move_to(LEFT * 4 + UP * 2.2)
        self.play(Write(cyl_label, run_time=1.5))

        # 画一个矩形卷曲成圆柱的示意
        rect = Rectangle(height=2, width=3, stroke_color=BLUE, stroke_width=2)
        rect.move_to(LEFT * 4 + DOWN * 0.2)
        self.play(ShowCreation(rect, run_time=1.5))

        arrow1 = Arrow(LEFT * 4 + UP * 0.8, LEFT * 4 + DOWN * 0.8, color=WHITE, buff=0.1)
        arrow1_label = Text("可展平", font_size=22, color=WHITE).next_to(arrow1, RIGHT, buff=0.2)
        self.play(ShowCreation(arrow1, run_time=1.2), Write(arrow1_label, run_time=1.2))

        # 右侧：球面不可展平
        sphere_label = Text("球面  K > 0", font_size=26, color=RED)
        sphere_label.move_to(RIGHT * 4 + UP * 2.2)
        self.play(Write(sphere_label, run_time=1.5))

        sphere = Circle(radius=1.2, color=RED, stroke_width=2)
        sphere.move_to(RIGHT * 4 + DOWN * 0.2)
        self.play(ShowCreation(sphere, run_time=1.5))

        cross = VGroup(
            Line(LEFT * 0.3 + UP * 0.3, RIGHT * 0.3 + DOWN * 0.3, color=RED, stroke_width=3),
            Line(LEFT * 0.3 + DOWN * 0.3, RIGHT * 0.3 + UP * 0.3, color=RED, stroke_width=3),
        )
        cross.move_to(RIGHT * 4 + DOWN * 1.6)
        no_text = Text("不可展平", font_size=22, color=RED).next_to(cross, DOWN, buff=0.15)
        self.play(FadeIn(cross, run_time=0.8), Write(no_text, run_time=1.2))

        self.wait(4.0)

        # 定理陈述
        theorem_box = Rectangle(height=1.6, width=10, stroke_color=GOLD, stroke_width=2)
        theorem_box.move_to(DOWN * 2.6)
        theorem_box.set_fill(BG_COLOR, opacity=0.8)

        theorem_text = Text("曲率 K 只依赖于曲面的内蕴几何", font_size=28, color=GOLD)
        theorem_text2 = Text("与如何嵌入三维空间无关", font_size=26, color=GOLD)
        theorem_text2.set_opacity(0.8)
        theorem_group = VGroup(theorem_text, theorem_text2).arrange(DOWN, buff=0.3)
        theorem_group.move_to(theorem_box.get_center())

        self.play(ShowCreation(theorem_box, run_time=1.5), Write(theorem_text, run_time=2.2))
        self.wait(2.0)
        self.play(Write(theorem_text2, run_time=1.8))
        self.wait(8.0)

        # 地图投影提示
        map_hint = Text("这就是为什么所有世界地图都必然有变形", font_size=24, color=BLUE)
        map_hint.next_to(theorem_box, DOWN, buff=0.4)
        self.play(FadeIn(map_hint, run_time=1.5))
        self.wait(10.0)

        self.play(FadeOut(VGroup(
            title, cyl_label, rect, arrow1, arrow1_label,
            sphere_label, sphere, cross, no_text,
            theorem_box, theorem_text, theorem_text2, map_hint
        )), run_time=2.2)
        self.wait(2.0)
