"""engines/manim/src/utils/timeline_helper.py
MaCode 关键帧 / 时间线构建器 — 为动画参数提供插值与导出。

用法::

    from utils.timeline_helper import Timeline, Keyframe

    timeline = Timeline()
    timeline.add(Keyframe(t=0.0, value=0, ease="linear"))
    timeline.add(Keyframe(t=1.0, value=1, ease="ease_in_out"))
    timeline.add(Keyframe(t=3.0, value=0.5, ease="ease_out"))

    v = timeline.at(1.5)   # 插值结果

    # 导出 CSV（供 ffmpeg 等外部工具使用）
    timeline.to_csv("keyframes.csv", fps=30)

    # 在 Manim updater 中使用
    def updater(mobject, dt):
        mobject.set_opacity(timeline.at(scene.time))
"""

import csv
import math
from collections.abc import Callable
from dataclasses import dataclass

# ------------------------------------------------------------------
# 1. 缓动函数
# ------------------------------------------------------------------

def _ease_linear(t: float) -> float:
    return t


def _ease_in(t: float) -> float:
    return t * t


def _ease_out(t: float) -> float:
    return 1 - (1 - t) * (1 - t)


def _ease_in_out(t: float) -> float:
    """Smoothstep 变体。"""
    if t < 0.5:
        return 2 * t * t
    else:
        return 1 - math.pow(-2 * t + 2, 2) / 2


def _ease_step(t: float) -> float:
    """阶梯函数：t < 1 返回 0，否则 1（用于离散切换）。"""
    return 0.0 if t < 1.0 else 1.0


_EASING_MAP: dict[str, Callable[[float], float]] = {
    "linear": _ease_linear,
    "ease_in": _ease_in,
    "ease_out": _ease_out,
    "ease_in_out": _ease_in_out,
    "step": _ease_step,
}


def _interpolate(a: float, b: float, t: float) -> float:
    """线性插值。"""
    return a + (b - a) * t


# ------------------------------------------------------------------
# 2. 关键帧
# ------------------------------------------------------------------

@dataclass
class Keyframe:
    """单个关键帧。

    Attributes:
        t: 时间（秒）
        value: 目标值（float）
        ease: 缓动名称，见 ``_EASING_MAP`` 的键
    """
    t: float
    value: float
    ease: str = "linear"

    def __post_init__(self):
        if self.ease not in _EASING_MAP:
            raise ValueError(f"Unknown ease '{self.ease}'. Supported: {list(_EASING_MAP.keys())}")


# ------------------------------------------------------------------
# 3. 时间线
# ------------------------------------------------------------------

class Timeline:
    """有序关键帧集合，支持任意时刻采样与 CSV 导出。"""

    def __init__(self):
        self._frames: list[Keyframe] = []

    def add(self, keyframe: Keyframe) -> "Timeline":
        """添加关键帧并自动按时间排序。

        支持链式调用::

            timeline.add(Keyframe(...)).add(Keyframe(...))
        """
        self._frames.append(keyframe)
        self._frames.sort(key=lambda k: k.t)
        return self

    def clear(self) -> "Timeline":
        """清空所有关键帧。"""
        self._frames.clear()
        return self

    def at(self, t: float) -> float:
        """在时刻 *t* 采样插值后的值。

        - 若 *t* 早于第一帧，返回第一帧的值。
        - 若 *t* 晚于最后一帧，返回最后一帧的值。
        - 否则在两帧之间按缓动函数插值。

        Args:
            t: 采样时间（秒）

        Returns:
            float: 插值结果
        """
        if not self._frames:
            return 0.0

        if t <= self._frames[0].t:
            return self._frames[0].value
        if t >= self._frames[-1].t:
            return self._frames[-1].value

        # 查找所在区间
        for i in range(len(self._frames) - 1):
            k0 = self._frames[i]
            k1 = self._frames[i + 1]
            if k0.t <= t <= k1.t:
                if k1.t == k0.t:
                    return k1.value
                local_t = (t - k0.t) / (k1.t - k0.t)
                eased_t = _EASING_MAP[k0.ease](local_t)
                return _interpolate(k0.value, k1.value, eased_t)

        # 兜底
        return self._frames[-1].value

    def to_csv(self, path: str, fps: int = 30, end_t: float | None = None) -> None:
        """将时间线采样为 CSV 文件。

        Args:
            path: 输出文件路径
            fps: 采样帧率
            end_t: 结束时间；默认使用最后一帧的时间
        """
        if not self._frames:
            return

        duration = end_t if end_t is not None else self._frames[-1].t
        frame_count = max(1, int(math.ceil(duration * fps)) + 1)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["frame", "time", "value"])
            for i in range(frame_count):
                t = i / fps
                writer.writerow([i, f"{t:.6f}", f"{self.at(t):.6f}"])

    def __len__(self) -> int:
        return len(self._frames)

    def __repr__(self) -> str:
        frames = ", ".join(f"({k.t}, {k.value}, {k.ease})" for k in self._frames)
        return f"Timeline([{frames}])"
