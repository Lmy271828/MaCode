"""scenes/11_vdgf_needham/shots/08_outro/scene.py
结尾：收束全片，升华主题。
"""

from manimlib import *

BG_COLOR = "#1A1A2E"
GOLD = "#E8D5B7"
BLUE = "#4A90E2"
RED = "#E74C3C"
GREEN = "#2ECC71"
WHITE = "#F0F0F0"

class OutroScene(Scene):
    def construct(self):
        # Background
        bg = Rectangle(width=20, height=12, fill_color="#1A1A2E", fill_opacity=1, stroke_width=0)
        bg.shift(UP * 0.5)
        self.add(bg)
        # 核心公式居中
        formula = Tex(r"\int_M K \, dA = 2\pi \, \chi(M)", font_size=52, color=GOLD)
        formula.move_to(UP * 0.5)

        # 五幕回顾
        acts = VGroup(
            Text("I   空间的本质", font_size=22, color=RED),
            Text("II  度量", font_size=22, color=GREEN),
            Text("III 曲率", font_size=22, color=GOLD),
            Text("IV  高斯-博内", font_size=22, color=BLUE),
            Text("V   形式", font_size=22, color=GOLD).set_opacity(0.8),
        )
        acts.arrange(RIGHT, buff=0.8)
        acts.move_to(UP * 2.3)

        self.play(FadeIn(acts, run_time=2.2))
        self.wait(2.0)
        self.play(Write(formula, run_time=3.0))
        self.wait(4.0)

        # 主题词
        keywords = Text("空间的本质 · 曲率的力量 · 形式的统一", font_size=28, color=WHITE)
        keywords.move_to(DOWN * 1.8)
        self.play(Write(keywords, run_time=2.2))
        self.wait(4.0)

        # 邀请阅读
        invite = Text("Tristan Needham 原著邀你深入这场数学正剧", font_size=24, color=GOLD).set_opacity(0.7)
        invite.move_to(DOWN * 2.8)
        self.play(FadeIn(invite, run_time=1.8))
        self.wait(12.0)

        # 淡出
        self.play(FadeOut(VGroup(acts, formula, keywords, invite)), run_time=3.0)
        self.wait(2.0)
