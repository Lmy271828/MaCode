"""scenes/10_narrative_test/scene.py
NarrativeScene 叙事模式冒烟测试。

验证点：
1. definition_reveal 模板正确加载
2. stage() 按顺序播放 statement → visual → annotation → example
3. 对象自动进入模板指定的 zone
4. primary_zone_first_visual_within 规则生效
5. 跳过 requires 依赖时抛出 StageOrderError
"""

import sys
from pathlib import Path

from manimlib import *

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "engines" / "manimgl" / "src"))
from components.narrative_scene import NarrativeScene
from utils.narrative_validator import StageOrderError


class NarrativeBasicTest(NarrativeScene):
    """基础叙事测试：按 definition_reveal 模板顺序播放全部 stage。"""

    LAYOUT_PROFILE = "lecture_3zones"
    NARRATIVE_PROFILE = "definition_reveal"

    def construct(self):
        title = Text("极限的定义", font_size=48)
        self.stage("statement", title, run_time=0.5)

        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-2, 2, 1],
            axis_config={"stroke_color": BLUE},
        )
        self.stage("visual", axes, run_time=0.5)

        formula = Tex(r"\lim_{x\to a} f(x) = L")
        self.stage("annotation", formula, run_time=0.5)

        circle = Circle(radius=1.5, color=GREEN)
        self.stage("example", circle, run_time=0.5)

        self.wait(0.5)


class NarrativeOrderViolationTest(NarrativeScene):
    """顺序违规测试：跳过 statement 直接调用 visual，应抛 StageOrderError。"""

    LAYOUT_PROFILE = "lecture_3zones"
    NARRATIVE_PROFILE = "definition_reveal"

    def construct(self):
        try:
            axes = Axes(
                x_range=[-3, 3, 1],
                y_range=[-2, 2, 1],
                axis_config={"stroke_color": BLUE},
            )
            self.stage("visual", axes, run_time=0.5)
            fail_text = Text("FAIL: order constraint not enforced", color=RED)
            self.add(fail_text)
        except StageOrderError as e:
            ok = Text("PASS: " + str(e), font_size=24, color=GREEN)
            ok.to_edge(UP)
            self.add(ok)
            self.wait(1)


class NarrativeMustBeFirstViolationTest(NarrativeScene):
    """must_be_first 违规测试：先播放 statement，再重复播放 statement。"""

    LAYOUT_PROFILE = "lecture_3zones"
    NARRATIVE_PROFILE = "definition_reveal"

    def construct(self):
        title = Text("First Title", font_size=36)
        self.stage("statement", title, run_time=0.5)
        try:
            title2 = Text("Second Title", font_size=36)
            self.stage("statement", title2, run_time=0.5)
            fail_text = Text("FAIL: must_be_first not enforced on replay", color=RED)
            self.add(fail_text)
        except StageOrderError as e:
            ok = Text("PASS: " + str(e), font_size=20, color=GREEN)
            ok.to_edge(UP)
            self.add(ok)
            self.wait(1)
