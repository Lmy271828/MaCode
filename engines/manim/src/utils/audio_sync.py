"""engines/manim/src/utils/audio_sync.py
MaCode AudioSync 适配层 — ManimCE 版本。

读取 pipeline/audio-analyze.sh 生成的 timeline.csv，
提供时间查询接口，让场景动画与音乐节拍同步。

用法:
    from utils.audio_sync import AudioSync

    class MyScene(Scene):
        def construct(self):
            sync = AudioSync("assets/bgm_timeline.csv")
            for t in np.arange(0, 10, 1/30):
                feat = sync.at(t)
                intensity = feat["loudness"]
                # 用 intensity 驱动动画...
"""

import csv
from pathlib import Path


class AudioSync:
    """音频节拍同步器。"""

    def __init__(self, csv_path):
        """加载 timeline.csv。

        Args:
            csv_path: timeline.csv 文件路径（绝对或相对场景目录）
        """
        self.data = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.data.append({
                    "time": float(row["time"]),
                    "beat": int(row["beat"]),
                    "loudness": float(row["loudness"]),
                    "low": float(row["low"]),
                    "mid": float(row["mid"]),
                    "high": float(row["high"]),
                })
        self.fps = self._infer_fps()

    def _infer_fps(self):
        """从时间戳推断帧率。"""
        if len(self.data) < 2:
            return 30
        dt = self.data[1]["time"] - self.data[0]["time"]
        return round(1.0 / dt) if dt > 0 else 30

    def _index(self, t):
        """时间 → 数组索引。"""
        idx = int(t * self.fps)
        return max(0, min(idx, len(self.data) - 1))

    def at(self, t):
        """获取时间 t 的完整音频特征。

        Returns:
            dict: {time, beat, loudness, low, mid, high}
        """
        return dict(self.data[self._index(t)])

    def loudness(self, t):
        """整体响度（0.0 ~ 1.0）。"""
        return self.data[self._index(t)]["loudness"]

    def low(self, t):
        """低频能量（鼓点）。"""
        return self.data[self._index(t)]["low"]

    def mid(self, t):
        """中频能量（人声/乐器）。"""
        return self.data[self._index(t)]["mid"]

    def high(self, t):
        """高频能量（镲片/高频）。"""
        return self.data[self._index(t)]["high"]

    def is_beat(self, t):
        """当前时间是否落在节拍上。"""
        return bool(self.data[self._index(t)]["beat"])

    def beat_time(self, n):
        """第 n 个节拍的时间点（从 0 开始）。

        Args:
            n: 节拍序号（0 = 第一个节拍）

        Returns:
            float or None: 时间（秒），如果没有则返回 None
        """
        count = 0
        for row in self.data:
            if row["beat"]:
                if count == n:
                    return row["time"]
                count += 1
        return None

    def beat_count(self):
        """检测到的总节拍数。"""
        return sum(1 for row in self.data if row["beat"])

    def tempo(self, t, window=1.0):
        """局部速度倍率（基于最近 window 秒内的节拍密度）。

        Returns:
            float: ~0.5（慢） ~ 2.0（快），用于动态调整动画速度
        """
        t0 = max(0, t - window / 2)
        t1 = t + window / 2
        beats_in_window = sum(
            1 for row in self.data
            if t0 <= row["time"] <= t1 and row["beat"]
        )
        # 假设正常 BPM 为 120（每秒 2 拍），标准化
        expected = window * 2.0
        ratio = (beats_in_window / expected) if expected > 0 else 1.0
        return max(0.5, min(2.0, ratio))
