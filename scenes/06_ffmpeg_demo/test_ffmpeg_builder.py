"""scenes/06_ffmpeg_demo/test_ffmpeg_builder.py
ffmpeg_builder 验证脚本。

验证点：
1. FFMpeg 流式 API 生成命令
2. 视频 fade in/out、scale 720p、fps 24
3. AudioBuilder 音频操作别名
4. 复杂 filtergraph（concat）字符串生成
5. fade_out 自动计算 start（ffprobe）
"""

import os
import subprocess
import sys
import tempfile

# 确保 utils 路径可用
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../engines/manim/src"))

from utils.ffmpeg_builder import FFMpeg
from utils.audio_builder import AudioBuilder


def _make_dummy_video(path: str, duration: int = 2):
    """用 ffmpeg 生成一个纯色测试视频。"""
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c=red:s=320x240:d={duration}",
            "-pix_fmt", "yuv420p",
            path,
        ],
        check=True,
        capture_output=True,
    )


def test_basic_command_generation():
    """测试基本命令生成。"""
    cmd = (
        FFMpeg()
        .input("video.mp4")
        .video.fade(type="in", duration=0.5)
        .video.fade(type="out", start=9.5, duration=0.5)
        .audio.afade(type="in", duration=0.5)
        .output("out.mp4", vcodec="libx264", acodec="aac")
    )

    args = cmd.build()
    assert args[0] == "ffmpeg"
    assert "-i" in args
    assert "video.mp4" in args
    assert "-vf" in args
    vf_idx = args.index("-vf")
    vf = args[vf_idx + 1]
    assert "fade=t=in:st=0:d=0.5" in vf
    assert "fade=t=out:st=9.5:d=0.5" in vf
    assert "-af" in args
    af_idx = args.index("-af")
    af = args[af_idx + 1]
    assert "afade=t=in:st=0:d=0.5" in af
    assert "out.mp4" in args
    print("[test] basic_command_generation PASSED")


def test_video_processing():
    """测试视频处理：fade in/out + scale 720p + fps 24。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = os.path.join(tmpdir, "src.mp4")
        dst = os.path.join(tmpdir, "dst.mp4")
        _make_dummy_video(src, duration=2)

        cmd = (
            FFMpeg()
            .global_option("-y")
            .input(src)
            .video.fade(type="in", duration=0.3)
            .video.fade(type="out", duration=0.3)  # 自动计算 start
            .video.scale(1280, 720)
            .video.fps(24)
            .output(dst, vcodec="libx264", acodec="aac", pix_fmt="yuv420p")
        )

        # 验证命令字符串
        command_str = cmd.command()
        assert "fade=t=in:st=0:d=0.3" in command_str
        assert "scale=1280:720" in command_str
        assert "fps=24" in command_str
        print(f"[test] generated command: {command_str}")

        # 实际执行 ffmpeg 验证
        subprocess.run(cmd.build(), check=True, capture_output=True)
        assert os.path.exists(dst), f"Output not found: {dst}"
        print("[test] video_processing PASSED")


def test_audio_builder():
    """测试 AudioBuilder 便利包装器。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = os.path.join(tmpdir, "src.mp4")
        dst = os.path.join(tmpdir, "dst.m4a")
        _make_dummy_video(src, duration=1)

        cmd = (
            AudioBuilder()
            .input_audio(src)
            .fade(type="in", duration=0.2)
            .trim(start=0.1, end=0.8)
            .vol(0.9)
            .output_audio(dst)
        )

        args = cmd.build()
        assert "-vn" in args
        assert "afade=t=in:st=0:d=0.2" in " ".join(args)
        assert "atrim=start=0.1:end=0.8" in " ".join(args)
        assert "volume=0.9" in " ".join(args)
        print("[test] audio_builder PASSED")


def test_complex_filtergraph():
    """测试复杂 filtergraph（concat）生成。"""
    cmd = (
        FFMpeg()
        .input("seg0.mp4")
        .input("seg1.mp4")
        .filter_complex(
            "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[vout][aout]"
        )
        .output("merged.mp4", vcodec="libx264", acodec="aac")
    )
    args = cmd.build()
    assert "-filter_complex" in args
    fc_idx = args.index("-filter_complex")
    assert "concat=n=2:v=1:a=1" in args[fc_idx + 1]
    print("[test] complex_filtergraph PASSED")


def test_validation():
    """测试参数校验。"""
    try:
        FFMpeg().input("x.mp4").video.fade(type="invalid", duration=1.0)
        assert False, "Expected ValueError for invalid fade type"
    except ValueError as exc:
        assert "in" in str(exc) and "out" in str(exc)

    try:
        FFMpeg().input("x.mp4").audio.afade(type="bad", duration=1.0)
        assert False, "Expected ValueError for invalid afade type"
    except ValueError as exc:
        assert "in" in str(exc) and "out" in str(exc)

    print("[test] validation PASSED")


def test_auto_fade_out_start():
    """测试 fade_out start 自动计算（ffprobe）。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = os.path.join(tmpdir, "src.mp4")
        # 生成 3 秒测试视频
        _make_dummy_video(src, duration=3)

        cmd = (
            FFMpeg()
            .global_option("-y")
            .input(src)
            .video.fade(type="out", duration=0.5)
            .output(os.path.join(tmpdir, "out.mp4"))
        )

        # 构建前 start 为 -1（标记值）
        # 构建后应自动计算为 3 - 0.5 = 2.5
        args = cmd.build()
        vf_idx = args.index("-vf")
        vf = args[vf_idx + 1]
        assert "fade=t=out:st=2.5:d=0.5" in vf, f"Unexpected vf: {vf}"
        print("[test] auto_fade_out_start PASSED")


if __name__ == "__main__":
    test_basic_command_generation()
    test_video_processing()
    test_audio_builder()
    test_complex_filtergraph()
    test_validation()
    test_auto_fade_out_start()
    print("\n[test] All ffmpeg_builder tests PASSED")
