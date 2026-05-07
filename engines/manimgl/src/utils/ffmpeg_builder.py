"""engines/manimgl/src/utils/ffmpeg_builder.py
FFmpeg command builder — lets Coding Agents avoid hand-writing -vf "fade=t=in:st=0:d=0.5" strings.

Provides fluent API supporting common video/audio filters and complex filtergraphs.
"""

import re
import shlex
import subprocess
from typing import List, Optional, Union


# ------------------------------------------------------------------
# 1. Filter chain builders
# ------------------------------------------------------------------

class _FilterBuilder:
    """Base filter chain builder."""

    def __init__(self):
        self._filters: List[str] = []

    def _add(self, expr: str):
        self._filters.append(expr)
        return self

    def build(self) -> str:
        """Join all filters with commas."""
        return ",".join(self._filters)


class VideoFilterBuilder(_FilterBuilder):
    """Video filter chain builder (-vf)."""

    def fade(self, type: str, duration: float, start: Optional[float] = None):
        """fade filter: fade in / out.

        Args:
            type: "in" or "out"
            duration: fade duration in seconds
            start: start time in seconds; for fade out, if not provided, auto-compute from video tail

        Returns:
            VideoFilterBuilder: self, supports chaining
        """
        if type not in ("in", "out"):
            raise ValueError(f"fade type must be 'in' or 'out', got {type!r}")
        if start is None:
            # fade_in defaults to 0; fade_out marked for auto-computation
            start = 0 if type == "in" else -1
        expr = f"fade=t={type}:st={start}:d={duration}"
        return self._add(expr)

    def scale(self, w: Union[int, str], h: Union[int, str]):
        """scale filter: adjust resolution."""
        return self._add(f"scale={w}:{h}")

    def crop(self, w: Union[int, str], h: Union[int, str], x: int = 0, y: int = 0):
        """crop filter: crop frame."""
        return self._add(f"crop={w}:{h}:{x}:{y}")

    def fps(self, n: Union[int, float]):
        """fps filter: set frame rate."""
        return self._add(f"fps={n}")

    def format(self, pix_fmt: str):
        """format filter: set pixel format."""
        return self._add(f"format={pix_fmt}")

    def trim(self, start: Optional[float] = None, end: Optional[float] = None):
        """trim filter: trim video segment."""
        parts = []
        if start is not None:
            parts.append(f"start={start}")
        if end is not None:
            parts.append(f"end={end}")
        return self._add(f"trim={':'.join(parts)}")

    def setpts(self, expr: str = "PTS-STARTPTS"):
        """setpts filter: reset timestamps."""
        return self._add(f"setpts={expr}")


class AudioFilterBuilder(_FilterBuilder):
    """Audio filter chain builder (-af)."""

    def afade(self, type: str, duration: float, start: Optional[float] = None):
        """afade filter: audio fade in / out.

        Args:
            type: "in" or "out"
            duration: fade duration in seconds
            start: start time in seconds; for afade out, if not provided, auto-compute from tail

        Returns:
            AudioFilterBuilder: self, supports chaining
        """
        if type not in ("in", "out"):
            raise ValueError(f"afade type must be 'in' or 'out', got {type!r}")
        if start is None:
            start = 0 if type == "in" else -1
        expr = f"afade=t={type}:st={start}:d={duration}"
        return self._add(expr)

    def atrim(self, start: Optional[float] = None, end: Optional[float] = None):
        """atrim filter: trim audio segment."""
        parts = []
        if start is not None:
            parts.append(f"start={start}")
        if end is not None:
            parts.append(f"end={end}")
        return self._add(f"atrim={':'.join(parts)}")

    def asetpts(self, expr: str = "PTS-STARTPTS"):
        """asetpts filter: reset audio timestamps."""
        return self._add(f"asetpts={expr}")

    def amix(self, inputs: int = 2):
        """amix filter: mix multiple audio streams."""
        return self._add(f"amix=inputs={inputs}")

    def volume(self, gain: Union[float, str]):
        """volume filter: adjust volume."""
        return self._add(f"volume={gain}")


# ------------------------------------------------------------------
# 2. Core builder
# ------------------------------------------------------------------

class _FilterProxy:
    """Filter proxy: forwards FilterBuilder method calls but returns FFMpeg itself for fluent API."""

    def __init__(self, ffmpeg: "FFMpeg", builder: _FilterBuilder):
        self._ffmpeg = ffmpeg
        self._builder = builder

    def __getattr__(self, name: str):
        real = getattr(self._builder, name)
        if not callable(real):
            return real

        def wrapper(*args, **kwargs):
            real(*args, **kwargs)
            return self._ffmpeg
        return wrapper


class FFMpeg:
    """FFmpeg command builder.

    Example::

        cmd = FFMpeg() \\
            .input("video.mp4") \\
            .video.fade(type="in", duration=0.5) \\
            .video.fade(type="out", start=9.5, duration=0.5) \\
            .audio.afade(type="in", duration=0.5) \\
            .output("out.mp4", vcodec="libx264", acodec="aac")

        cmd.build()   # -> list of command args for subprocess
        cmd.command() # -> full shell command string
    """

    def __init__(self):
        self._inputs: List[str] = []
        self._video = VideoFilterBuilder()
        self._audio = AudioFilterBuilder()
        self._filter_complex: Optional[str] = None
        self._output_path: Optional[str] = None
        self._output_options: dict = {}
        self._global_options: List[str] = []
        self._duration: Optional[float] = None  # cached duration to avoid repeated ffprobe

    @property
    def video(self) -> "_FilterProxy":
        """Video filter accessor."""
        return _FilterProxy(self, self._video)

    @property
    def audio(self) -> "_FilterProxy":
        """Audio filter accessor."""
        return _FilterProxy(self, self._audio)

    def input(self, path: str):
        """Add input file.

        Args:
            path: input media file path

        Returns:
            FFMpeg: self, supports chaining
        """
        self._inputs.append(path)
        return self

    def filter_complex(self, expr: str):
        """Set complex filter graph (-filter_complex).

        Setting this overrides simple -vf / -af filter chains.
        """
        self._filter_complex = expr
        return self

    def append_filter_complex(self, expr: str):
        """Append complex filter graph expression (semicolon-separated)."""
        if self._filter_complex is None:
            self._filter_complex = expr
        else:
            self._filter_complex = f"{self._filter_complex};{expr}"
        return self

    def output(self, path: str, **options):
        """Set output file and encoding options.

        Args:
            path: output file path
            **options: encoding options, e.g. ``vcodec="libx264"``, ``acodec="aac"``, ``crf=23``, etc.

        Returns:
            FFMpeg: self, supports chaining
        """
        self._output_path = path
        self._output_options = options
        return self

    def global_option(self, *args: str):
        """Add global options, e.g. ``-y``, ``-hide_banner``, etc."""
        self._global_options.extend(args)
        return self

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _probe_duration(self, input_path: str) -> float:
        """Query media duration in seconds using ffprobe."""
        if self._duration is not None:
            return self._duration
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    input_path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            self._duration = float(result.stdout.strip())
            return self._duration
        except Exception as exc:
            raise RuntimeError(
                f"Failed to probe duration for {input_path}: {exc}"
            ) from exc

    def _resolve_fade_starts(self):
        """Resolve and auto-fill fade_out / afade_out start parameters."""
        if not self._inputs:
            return

        # Video fade_out auto-computation
        for i, filt in enumerate(self._video._filters):
            if filt.startswith("fade=t=out:") and ":st=-1:" in filt:
                dur = self._probe_duration(self._inputs[0])
                m = re.search(r":d=([0-9.]+)", filt)
                if m:
                    fdur = float(m.group(1))
                    start = max(0.0, dur - fdur)
                    self._video._filters[i] = f"fade=t=out:st={start}:d={fdur}"

        # Audio afade_out auto-computation
        for i, filt in enumerate(self._audio._filters):
            if filt.startswith("afade=t=out:") and ":st=-1:" in filt:
                dur = self._probe_duration(self._inputs[0])
                m = re.search(r":d=([0-9.]+)", filt)
                if m:
                    fdur = float(m.group(1))
                    start = max(0.0, dur - fdur)
                    self._audio._filters[i] = f"afade=t=out:st={start}:d={fdur}"

    def build(self) -> List[str]:
        """Build into subprocess argument list.

        Returns:
            list[str]: argument list ready for ``subprocess.run([...])``
        """
        self._resolve_fade_starts()

        args: List[str] = ["ffmpeg"]
        args.extend(self._global_options)

        for inp in self._inputs:
            args.extend(["-i", inp])

        if self._filter_complex is not None:
            args.extend(["-filter_complex", self._filter_complex])
        else:
            vf = self._video.build()
            if vf:
                args.extend(["-vf", vf])
            af = self._audio.build()
            if af:
                args.extend(["-af", af])

        if self._output_path:
            for k, v in self._output_options.items():
                args.extend([f"-{k}", str(v)])
            args.append(self._output_path)

        return args

    def command(self) -> str:
        """Build into executable shell command string.

        Returns:
            str: properly escaped shell command
        """
        return " ".join(shlex.quote(str(arg)) for arg in self.build())
