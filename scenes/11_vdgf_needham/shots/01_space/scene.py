"""scenes/11_vdgf_needham/shots/01_space/scene.py
三种几何：欧几里得、球面、双曲几何的平行公设对比。
"""

from manimlib import *

BG_COLOR = "#1A1A2E"
GOLD = "#E8D5B7"
BLUE = "#4A90E2"
RED = "#E74C3C"
GREEN = "#2ECC71"
WHITE = "#F0F0F0"

class ThreeGeometriesScene(Scene):
    def construct(self):
        # Background
        bg = Rectangle(width=20, height=12, fill_color="#1A1A2E", fill_opacity=1, stroke_width=0)
        bg.shift(UP * 0.5)
        self.add(bg)

        title = Text("Act I  空间的本质 —— 三种几何", font_size=40, color=GOLD)
        title.to_edge(UP, buff=0.4)
        self.play(Write(title, run_time=2.2))
        self.wait(2.0)

        # 三个面板
        euclidean = self.make_panel("欧几里得几何", BLUE, self.euclidean_content)
        spherical = self.make_panel("球面几何", RED, self.spherical_content)
        hyperbolic = self.make_panel("双曲几何", GREEN, self.hyperbolic_content)

        panels = VGroup(euclidean, spherical, hyperbolic)
        panels.arrange(RIGHT, buff=0.8)
        panels.move_to(DOWN * 0.2)

        self.play(FadeIn(euclidean, run_time=1.8))
        self.wait(2.0)
        self.play(FadeIn(spherical, run_time=1.8))
        self.wait(2.0)
        self.play(FadeIn(hyperbolic, run_time=1.8))
        self.wait(4.0)

        # 平行公设文字对比
        axiom_text = Text("平行公设的三种命运", font_size=28, color=GOLD)
        axiom_text.next_to(panels, DOWN, buff=0.6)
        self.play(Write(axiom_text, run_time=1.5))

        axioms = VGroup(
            Text("唯一平行线：1条", color=BLUE),
            Text("无平行线：0条", color=RED),
            Text("无穷平行线：∞条", color=GREEN),
        )
        axioms.arrange(RIGHT, buff=1.2)
        axioms.next_to(axiom_text, DOWN, buff=0.3)
        self.play(FadeIn(axioms, run_time=2.2))
        self.wait(8.0)

        # 三角形内角和
        angle_title = Text("三角形内角和", font_size=26, color=WHITE)
        angle_title.next_to(axioms, DOWN, buff=0.5)
        self.play(Write(angle_title, run_time=1.2))

        angles = VGroup(
            Tex(r"= \pi", color=BLUE),
            Tex(r"> \pi", color=RED),
            Tex(r"< \pi", color=GREEN),
        )
        angles.arrange(RIGHT, buff=1.8)
        angles.next_to(angle_title, DOWN, buff=0.3)
        self.play(FadeIn(angles, run_time=1.8))
        self.wait(12.0)

        self.play(FadeOut(VGroup(title, panels, axiom_text, axioms, angle_title, angles)), run_time=2.2)
        self.wait(2.0)

    def make_panel(self, label, color, content_fn):
        rect = Rectangle(height=4.5, width=4.2, stroke_color=color, stroke_width=2)
        rect.set_fill(BG_COLOR, opacity=1)
        label_text = Text(label, font_size=24, color=color)
        label_text.next_to(rect.get_top(), DOWN, buff=0.3)
        content = content_fn()
        content.move_to(rect.get_center() + DOWN * 0.2)
        return VGroup(rect, label_text, content)

    def euclidean_content(self):
        # 两条平行线 + 一条截线
        l1 = Line(LEFT * 1.5 + UP * 0.5, RIGHT * 1.5 + UP * 0.5, color=BLUE, stroke_width=2)
        l2 = Line(LEFT * 1.5 + DOWN * 0.5, RIGHT * 1.5 + DOWN * 0.5, color=BLUE, stroke_width=2)
        transversal = Line(LEFT * 0.3 + UP * 0.8, LEFT * 0.3 + DOWN * 0.8, color=WHITE, stroke_width=1.5)
        # 同位角标记
        arc1 = Arc(0.3, PI/2, PI/6, color=GOLD, stroke_width=1.5).move_arc_center_to(LEFT*0.3 + UP*0.5)
        arc2 = Arc(0.3, PI/2, PI/6, color=GOLD, stroke_width=1.5).move_arc_center_to(LEFT*0.3 + DOWN*0.5)
        return VGroup(l1, l2, transversal, arc1, arc2)

    def spherical_content(self):
        # 球面上的大圆（用圆表示）
        circle = Circle(radius=1.3, color=RED, stroke_width=2)
        # 两条"直线"（大圆）相交
        great1 = Arc(1.3, 0, PI, color=RED, stroke_width=2)
        great2 = Arc(1.3, PI/3, PI, color=RED, stroke_width=2)
        great2.set_stroke(opacity=0.7)
        great2.rotate(PI/2, axis=OUT, about_point=ORIGIN)
        # 交点
        dot = Dot(radius=0.06, color=GOLD)
        return VGroup(circle, great1, great2, dot)

    def hyperbolic_content(self):
        # 双曲平面的庞加莱圆盘模型示意
        disk = Circle(radius=1.3, color=GREEN, stroke_width=2)
        # 几条"直线"（垂直于边界的圆弧或直径）
        line1 = Line(UP * 1.2, DOWN * 1.2, color=GREEN, stroke_width=1.5)
        arc1 = ArcBetweenPoints(LEFT*0.8 + UP*0.3, LEFT*0.8 + DOWN*0.3, angle=PI/3, color=GREEN, stroke_width=1.5)
        arc1.set_stroke(opacity=0.7)
        arc2 = ArcBetweenPoints(RIGHT*0.8 + UP*0.3, RIGHT*0.8 + DOWN*0.3, angle=-PI/3, color=GREEN, stroke_width=1.5)
        arc2.set_stroke(opacity=0.7)
        # 一个点
        pt = Dot(radius=0.06, color=GOLD).move_to(LEFT * 0.1)
        return VGroup(disk, line1, arc1, arc2, pt)
