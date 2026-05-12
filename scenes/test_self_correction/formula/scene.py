"""scenes/test_self_correction/formula/scene.py
Formula segment — derivation of a^2 + b^2 = c^2.

This segment is layout-correct (no B1/B2/B3 errors).
"""
from manim import *
from templates.scene_base import MaCodeScene


class FormulaScene(MaCodeScene):
    # @segment:formula
    # @time:0.0-4.0s
    # @keyframes:[0.0, 2.0, 4.0]
    # @description:Formula derivation step by step
    def construct(self):
        title = Text("Pythagorean Theorem", font_size=48)
        title.to_edge(UP, buff=0.8)

        formula = MathTex("a^2 + b^2 = c^2", font_size=72)
        formula.move_to([0, 1, 0])

        label = Text("Equation:", font_size=36)
        label.next_to(formula, LEFT, buff=0.5)

        derived = MathTex("c = \\sqrt{a^2 + b^2}", font_size=72)
        derived.next_to(formula, DOWN, buff=0.8)

        self.play(Write(title), run_time=0.8)
        self.play(Write(label), run_time=0.8)
        self.play(Write(formula), run_time=1.0)
        self.wait(0.4)
        self.play(Write(derived), run_time=1.0)
        self.wait(0.5)
