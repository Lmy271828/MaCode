"""Intro segment of composite demo."""

import json
import os

from manim import *
from templates.scene_base import MaCodeScene


class IntroScene(MaCodeScene):
    def construct(self):
        # 读取 composite manifest 注入的参数
        params = {}
        params_file = os.environ.get("MACODE_PARAMS_JSON", "")
        if params_file and os.path.isfile(params_file):
            with open(params_file) as f:
                params = json.load(f)

        title_text = params.get("title_text", "Composite Demo")
        theme_color = params.get("theme_color", "#FFFFFF")

        title = Text(title_text, font_size=48, color=theme_color)
        title.to_edge(UP)
        self.play(FadeIn(title), run_time=0.8)
        self.wait(0.3)
