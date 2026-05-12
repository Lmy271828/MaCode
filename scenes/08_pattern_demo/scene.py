"""scenes/08_pattern_demo/scene.py
Pattern + Timeline 辅助工具演示场景。

验证点：
1. pattern_helper — 正则模式工厂提取数字、单位、时间戳
2. timeline_helper — 关键帧插值驱动 mobject 透明度变化
"""

from manim import *
from utils.pattern_helper import pattern
from utils.timeline_helper import Keyframe, Timeline


class PatternDemoScene(Scene):
    def construct(self):
        # ── 1. 原始文本 ──
        raw_text = (
            "Data: 42 items, speed -3.14e2 m/s, "
            "elapsed 12:34:56.789, progress 75.5%"
        )
        text_mobj = Text(raw_text, font_size=28)
        text_mobj.to_edge(UP, buff=0.5)
        self.play(Write(text_mobj), run_time=1)
        self.wait(0.3)

        # ── 2. 用 pattern_helper 提取各类 token ──
        tokens = []

        # 整数
        for m in pattern.compile(pattern.number.int()).finditer(raw_text):
            tokens.append((m.group(), m.start(), m.end(), YELLOW))

        # 浮点数 / 科学计数法
        float_pat = pattern.number.float()
        for m in pattern.compile(float_pat).finditer(raw_text):
            # 避免重复匹配已被 int 匹配到的子串（简单过滤：长度大于 int 模式）
            if "." in m.group() or "e" in m.group() or "E" in m.group():
                tokens.append((m.group(), m.start(), m.end(), BLUE))

        # 百分数
        for m in pattern.compile(pattern.number.percent()).finditer(raw_text):
            tokens.append((m.group(), m.start(), m.end(), GREEN))

        # 时间戳
        for m in pattern.compile(pattern.time.hms()).finditer(raw_text):
            tokens.append((m.group(), m.start(), m.end(), ORANGE))

        # 单位 m/s
        for m in pattern.compile(pattern.unit("m/s")).finditer(raw_text):
            tokens.append((m.group(), m.start(), m.end(), RED))

        # 去重并按起始位置排序
        seen = set()
        unique_tokens = []
        for tok in sorted(tokens, key=lambda x: x[1]):
            key = (tok[1], tok[2])
            if key not in seen:
                seen.add(key)
                unique_tokens.append(tok)

        # 高亮显示提取结果
        highlights = VGroup()
        for value, _, _, color in unique_tokens:
            lbl = Text(value, font_size=32, color=color)
            highlights.add(lbl)

        highlights.arrange(RIGHT, buff=0.4)
        highlights.next_to(text_mobj, DOWN, buff=0.6)
        self.play(FadeIn(highlights, shift=DOWN), run_time=1)
        self.wait(0.3)

        # ── 3. Timeline 驱动透明度动画 ──
        timeline = Timeline()
        timeline.add(Keyframe(t=0.0, value=1.0, ease="linear"))
        timeline.add(Keyframe(t=1.5, value=0.2, ease="ease_in_out"))
        timeline.add(Keyframe(t=3.0, value=1.0, ease="ease_out"))

        indicator = Square(side_length=1.5, color=PURPLE, fill_opacity=0.5)
        indicator.next_to(highlights, DOWN, buff=0.8)
        self.play(Create(indicator), run_time=0.5)

        # 使用 updater 绑定 timeline
        start_time = self.time

        def opacity_updater(mob):
            t = self.time - start_time
            if t > 3.0:
                t = 3.0
            mob.set_opacity(timeline.at(t))

        indicator.add_updater(opacity_updater)
        self.wait(3.2)
        indicator.remove_updater(opacity_updater)

        # ── 4. 淡出 ──
        self.play(FadeOut(*self.mobjects), run_time=0.8)
