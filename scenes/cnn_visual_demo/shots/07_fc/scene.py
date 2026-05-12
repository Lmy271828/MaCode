"""CNN Visual Demo — FC Segment (30s)

Flatten + Fully Connected + Softmax classification.
"""

from manimlib import *
from templates.scene_base import MaCodeScene


class FcScene(MaCodeScene):
    def construct(self):
        self.camera.background_rgb = [0.05, 0.05, 0.08]

        title = Text("全连接层 + 分类输出", font_size=32, color=GREY_B)
        title.to_edge(UP, buff=0.5)
        self.play(FadeIn(title), run_time=0.5)

        # Feature vector
        vec_group = VGroup()
        for i in range(8):
            sq = Square(side_length=0.3)
            sq.set_fill(BLUE, opacity=0.6)
            sq.set_stroke(BLUE, width=1)
            sq.move_to(LEFT * 4 + DOWN * 1.5 + UP * i * 0.35)
            vec_group.add(sq)

        vec_label = Text("展平特征向量", font_size=16, color=GREY_B)
        vec_label.next_to(vec_group, LEFT, buff=0.2)

        self.play(FadeIn(vec_group), FadeIn(vec_label), run_time=0.5)

        # FC layer
        fc_group = VGroup()
        for i in range(5):
            circ = Circle(radius=0.2, color=GREEN)
            circ.set_fill(GREEN, opacity=0.4)
            circ.move_to(LEFT * 0.5 + DOWN * 1 + UP * i * 0.5)
            fc_group.add(circ)

        fc_label = Text("FC 层", font_size=16, color=GREY_B)
        fc_label.next_to(fc_group, LEFT, buff=0.2)

        # Arrows from vec to fc
        for fc in fc_group:
            for v in vec_group:
                line = Line(v.get_right(), fc.get_left(), color=GREY_D, stroke_width=0.5, opacity=0.3)
                self.add(line)

        self.play(FadeIn(fc_group), FadeIn(fc_label), run_time=0.5)

        # Output classes
        classes = ["猫", "狗", "鸟", "车", "船"]
        out_group = VGroup()
        probs = [0.05, 0.75, 0.05, 0.10, 0.05]
        for i, (cls, prob) in enumerate(zip(classes, probs)):
            rect = Rectangle(height=0.35, width=prob * 3 + 0.3)
            rect.set_fill(GREEN if prob > 0.5 else GREY, opacity=0.7)
            rect.set_stroke(WHITE, width=1)
            rect.move_to(RIGHT * 3.5 + DOWN * 1 + UP * i * 0.5)
            label = Text(f"{cls}: {prob:.0%}", font_size=14, color=WHITE)
            label.move_to(rect.get_center())
            out_group.add(rect, label)

        out_label = Text("Softmax 输出", font_size=16, color=GREY_B)
        out_label.next_to(out_group, RIGHT, buff=0.2)

        arr = Arrow(fc_group.get_right(), out_group.get_left(), color=BLUE_C, buff=0.3)

        self.play(GrowArrow(arr), run_time=0.3)
        self.play(FadeIn(out_group), FadeIn(out_label), run_time=0.5)
        self.wait(1.0)

        # Highlight prediction
        pred_rect = out_group[0]  # 猫
        pred_rect.set_stroke(YELLOW, width=3)
        pred_text = Text("预测: 狗 (75%)", font_size=20, color=YELLOW)
        pred_text.to_edge(DOWN, buff=0.5)
        self.play(FadeIn(pred_text), run_time=0.5)
        self.wait(1.0)

        self.play(
            FadeOut(title), FadeOut(vec_group), FadeOut(vec_label),
            FadeOut(fc_group), FadeOut(fc_label),
            FadeOut(arr), FadeOut(out_group), FadeOut(out_label),
            FadeOut(pred_text), run_time=0.5,
        )
