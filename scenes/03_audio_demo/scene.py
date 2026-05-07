"""scenes/03_audio_demo/scene.py
Audio Sync 演示场景。

一个圆圈随音乐节拍跳动，低频能量驱动大小，节拍触发颜色闪烁。
同时显示低/中/高三个频谱条，实时反映音乐能量分布。

依赖:
    - engines/manim/src/utils/audio_sync.py
    - assets/beat_timeline.csv (由 pipeline/audio-analyze.sh 生成)
"""

import sys
from pathlib import Path

# 将 MaCode 适配层加入模块路径
sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent / "engines" / "manim" / "src")
)

from manim import *
from utils.audio_sync import AudioSync
import numpy as np


class AudioSyncDemo(Scene):
    def construct(self):
        # ── 加载音频同步数据 ──
        scene_dir = Path(__file__).parent
        sync = AudioSync(scene_dir / "assets" / "beat_timeline.csv")

        # ── 视觉元素 ──
        # 中央大圆：半径随低频能量跳动
        circle = Circle(radius=1.5, color=BLUE, fill_opacity=0.8)
        circle.move_to(ORIGIN)

        # 三个频谱条（低/中/高）
        bar_low = Rectangle(width=0.6, height=0.1, color=RED, fill_opacity=0.9)
        bar_mid = Rectangle(width=0.6, height=0.1, color=GREEN, fill_opacity=0.9)
        bar_high = Rectangle(width=0.6, height=0.1, color=YELLOW, fill_opacity=0.9)

        bar_low.move_to(DOWN * 2.5 + LEFT * 2)
        bar_mid.move_to(DOWN * 2.5)
        bar_high.move_to(DOWN * 2.5 + RIGHT * 2)

        # 标签
        label_low = Text("LOW", font_size=24).next_to(bar_low, DOWN)
        label_mid = Text("MID", font_size=24).next_to(bar_mid, DOWN)
        label_high = Text("HIGH", font_size=24).next_to(bar_high, DOWN)

        # 节拍指示器
        beat_indicator = Dot(radius=0.2, color=WHITE)
        beat_indicator.move_to(UP * 3)
        beat_indicator.set_opacity(0)

        self.add(circle, bar_low, bar_mid, bar_high,
                 label_low, label_mid, label_high, beat_indicator)

        # ── 动画循环（逐帧驱动） ──
        fps = 30
        duration = 10.0
        num_frames = int(duration * fps)

        for frame in range(num_frames):
            t = frame / fps
            feat = sync.at(t)

            # 低频驱动圆圈半径
            target_radius = 1.0 + feat["low"] * 2.0
            circle.set_width(target_radius * 2)

            # 节拍触发颜色闪烁
            if feat["beat"]:
                circle.set_color(RED)
                beat_indicator.set_opacity(1)
            else:
                circle.set_color(BLUE)
                beat_indicator.set_opacity(0)

            # 频谱条高度随能量变化
            bar_low.stretch_to_fit_height(0.1 + feat["low"] * 3.0)
            bar_low.move_to(DOWN * 2.5 + LEFT * 2 + UP * (0.1 + feat["low"] * 3.0) / 2)

            bar_mid.stretch_to_fit_height(0.1 + feat["mid"] * 3.0)
            bar_mid.move_to(DOWN * 2.5 + UP * (0.1 + feat["mid"] * 3.0) / 2)

            bar_high.stretch_to_fit_height(0.1 + feat["high"] * 3.0)
            bar_high.move_to(DOWN * 2.5 + RIGHT * 2 + UP * (0.1 + feat["high"] * 3.0) / 2)

            # 每帧等待 1/fps 秒
            self.wait(1 / fps)

        # 结束淡出
        self.play(FadeOut(circle, bar_low, bar_mid, bar_high,
                          label_low, label_mid, label_high, beat_indicator))
