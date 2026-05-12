"""scenes/09_zone_test/scene.py
ZoneScene 约束系统冒烟测试。

验证点：
1. 四个 zone 都能正确放置对象
2. place() 返回 mobject 支持链式调用
3. zone 类型约束生效（caption zone 拒绝 Circle）
4. primary zone 视觉对象检测生效
5. 不同 align 值正确映射到 zone 边缘
"""

from manimlib import *

# ZoneScene lives under engines/manimgl/src/components/
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "engines" / "manimgl" / "src"))
from components.zoned_scene import ZoneScene, ZoneTypeError, PrimaryZoneEmptyError


class ZoneBasicTest(ZoneScene):
    """基础放置测试：四个 zone 各放一个对象。"""

    def construct(self):
        # --- title zone ---
        title = Text("Zone Layout Demo", font_size=48)
        self.place(title, "title")

        # --- main_visual zone (primary) ---
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-2, 2, 1],
            axis_config={"stroke_color": BLUE},
        )
        self.place(axes, "main_visual")

        # --- annotation zone ---
        note = Text("注释区", font_size=24)
        self.place(note, "annotation")

        # --- caption zone ---
        formula = TexText(r"$E = mc^2$")
        self.place(formula, "caption")

        # 验证 primary zone 有视觉对象
        self.validate_primary_zone()

        # 简单动画
        self.play(ShowCreation(title), run_time=0.5)
        self.play(ShowCreation(axes), run_time=1.0)
        self.play(FadeIn(note), FadeIn(formula), run_time=0.5)
        self.wait(1)


class ZoneTypeConstraintTest(ZoneScene):
    """类型约束测试：尝试把 Circle 放进 caption zone，预期抛 ZoneTypeError。"""

    def construct(self):
        try:
            bad = Circle()
            self.place(bad, "caption")
            # 如果走到这里，说明约束失效
            fail_text = Text("FAIL: type constraint not enforced", color=RED)
            self.add(fail_text)
        except ZoneTypeError as e:
            ok = Text("PASS: " + str(e), font_size=24, color=GREEN)
            ok.to_edge(UP)
            self.add(ok)
            self.wait(2)


class ZoneOverflowTest(ZoneScene):
    """溢出测试：title zone max_objects=2，放第三个应抛 ZoneOverflowError。"""

    def construct(self):
        self.place(Text("Title 1", font_size=24), "title")
        self.place(Text("Title 2", font_size=24), "title")
        try:
            self.place(Text("Title 3", font_size=24), "title")
            fail_text = Text("FAIL: overflow not enforced", color=RED)
            self.add(fail_text)
        except Exception as e:
            ok = Text("PASS: " + str(e), font_size=20, color=GREEN)
            ok.to_edge(UP)
            self.add(ok)
            self.wait(2)


class ZoneAlignTest(ZoneScene):
    """对齐测试：同一 zone 内不同 align 值。"""

    def construct(self):
        # 在 main_visual zone 的四个边缘各放一个小圆
        self.place(Circle(radius=0.2, color=BLUE), "main_visual", align="top")
        self.place(Circle(radius=0.2, color=GREEN), "main_visual", align="bottom")
        self.place(Circle(radius=0.2, color=YELLOW), "main_visual", align="left")
        self.place(Circle(radius=0.2, color=RED), "main_visual", align="right")
        # 中心再放一个
        self.place(Circle(radius=0.3, color=WHITE), "main_visual", align="center")

        self.validate_primary_zone()

        self.play(*[ShowCreation(c) for c in self._zone_objects["main_visual"]], run_time=1)
        self.wait(1)
