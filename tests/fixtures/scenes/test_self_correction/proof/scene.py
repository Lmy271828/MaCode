"""scenes/test_self_correction/proof/scene.py
Proof segment — geometric proof of Pythagorean theorem.

INJECTED ERROR: A1 duration mismatch.
  Manifest declares 3.0s but animation sums to ~5.0s.
"""
from manim import *
from templates.scene_base import MaCodeScene


class ProofScene(MaCodeScene):
    # @segment:proof
    # @time:0.0-3.0s
    # @keyframes:[0.0, 2.0, 3.0]
    # @description:Geometric proof with squares and triangles
    def construct(self):
        A = np.array([0, 0, 0])  # noqa: N806
        B = np.array([3, 0, 0])  # noqa: N806
        C = np.array([0, 4, 0])  # noqa: N806

        triangle = Polygon(A, B, C, color=WHITE)
        triangle.set_fill(WHITE, opacity=0.2)

        square_ab = Polygon(
            A, B, B + np.array([0, -3, 0]), A + np.array([0, -3, 0]), color=BLUE
        )
        square_ab.set_fill(BLUE, opacity=0.4)

        square_ac = Polygon(
            A, C, C + np.array([-4, 0, 0]), A + np.array([-4, 0, 0]), color=GREEN
        )
        square_ac.set_fill(GREEN, opacity=0.4)

        square_bc = Polygon(
            B, C, C + np.array([-4, -3, 0]), B + np.array([-4, -3, 0]), color=RED
        )
        square_bc.set_fill(RED, opacity=0.4)

        # A1 ERROR: total ~5.0s while manifest claims 3.0s
        self.play(Create(triangle), run_time=1.5)
        self.wait(0.5)
        self.play(Create(square_ab), run_time=1.0)
        self.play(Create(square_ac), run_time=1.0)
        self.play(Create(square_bc), run_time=1.0)
