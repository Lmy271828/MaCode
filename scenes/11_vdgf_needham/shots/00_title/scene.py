"""scenes/11_vdgf_needham/shots/00_title/scene.py
标题场景：建立视觉基调，展示书名与作者。
"""

from manimlib import *

BG_COLOR = "#1A1A2E"
GOLD = "#E8D5B7"
BLUE = "#4A90E2"
RED = "#E74C3C"
GREEN = "#2ECC71"

class TitleScene(Scene):
    def construct(self):
        # Background
        bg = Rectangle(width=20, height=12, fill_color="#1A1A2E", fill_opacity=1, stroke_width=0)
        bg.shift(UP * 0.5)
        self.add(bg)
        # 装饰性球面网格线框（2D近似）
        sphere_group = VGroup()
        for r in np.linspace(0.5, 2.5, 5):
            c = Circle(radius=r, stroke_color=BLUE, stroke_width=1)
            c.set_stroke(opacity=0.15)
            sphere_group.add(c)
        for angle in np.linspace(0, PI, 6):
            ellipse = Ellipse(width=5, height=1.5, stroke_color=BLUE, stroke_width=1)
            ellipse.set_stroke(opacity=0.15)
            ellipse.rotate(angle, axis=OUT)
            sphere_group.add(ellipse)
        sphere_group.shift(LEFT * 4.5)
        self.add(sphere_group)

        # 书名
        title = Text("可视化微分几何和形式", font_size=64, color=GOLD)
        title.move_to(UP * 0.8)

        # 副标题
        subtitle = Text("一部五幕数学正剧", font_size=40, color=BLUE)
        subtitle.next_to(title, DOWN, buff=0.4)

        # 作者
        author = Text("Tristan Needham", font_size=32, color=GOLD)
        author.set_opacity(0.7)
        author.next_to(subtitle, DOWN, buff=0.6)

        # 核心概念提示
        hint = Text("核心概念巡礼 · 曲率 · 高斯-博内 · 微分形式", font_size=24, color=GOLD)
        hint.set_opacity(0.5)
        hint.move_to(DOWN * 2.2)

        # 动画序列
        self.play(FadeIn(title, run_time=3.0))
        self.wait(2.0)
        self.play(FadeIn(subtitle, run_time=2.2))
        self.wait(1.2)
        self.play(FadeIn(author, run_time=1.8))
        self.wait(1.2)
        self.play(FadeIn(hint, run_time=1.5))
        self.wait(8.0)

        # 五幕标签依次闪现
        acts = VGroup(
            Text("Act I  空间的本质", font_size=20, color=RED),
            Text("Act II  度量", font_size=20, color=GREEN),
            Text("Act III  曲率", font_size=20, color=GOLD),
            Text("Act IV  高斯-博内", font_size=20, color=BLUE),
            Text("Act V  形式", font_size=20, color=GOLD),
        )
        acts[-1].set_opacity(0.8)
        acts.arrange(RIGHT, buff=0.6)
        acts.move_to(DOWN * 3.0)
        acts.set_opacity(0)

        for act in acts:
            self.play(act.animate.set_opacity(0.6), run_time=0.9)
            self.wait(0.8)

        self.wait(12.0)
        self.play(FadeOut(VGroup(title, subtitle, author, hint, acts)), run_time=2.2)
        self.wait(2.0)
