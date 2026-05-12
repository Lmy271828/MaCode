#!/usr/bin/env python3
"""bin/composite-assemble.py
Pure execution layer for composite scene assembly.
Extracted from composite-render.py — performs ONLY sequential execution:
  overlay → transition/concat → audio → deliver → cache populate

Receives pre-computed parameters; makes NO decisions.

Usage:
    composite-assemble.py \
        --scene-dir <dir> \
        --segments '<json_array>' \
        --overlays '<json_array>' \
        --manifest <path> \
        --output <mp4> \
        [--json]

JSON segments format:
    [
      {"id": "intro", "video": "path/to/intro.mp4", "transition": {"type": "fade", "duration": 0.3}},
      {"id": "main", "video": "path/to/main.mp4"}
    ]

JSON overlays format:
    [
      {"base_segment": "intro", "foreground_segment": "overlay1", "start": 0, "duration": 2, "x": "0", "y": "0", "blend": "overlay"}
    ]
"""

import argparse
import json
import os
import subprocess
import sys


def get_project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_python() -> str:
    project_root = get_project_root()
    venv_python = os.path.join(project_root, ".venv", "bin", "python")
    if os.path.isfile(venv_python) and os.access(venv_python, os.X_OK):
        return venv_python
    return "python3"


def main():
    parser = argparse.ArgumentParser(
        description="Assemble composite segments into final video (execution layer).",
        usage="%(prog)s [options]",
        epilog="Examples:\n"
               "  %(prog)s --scene-dir scenes/04_demo --segments '[{\"video\":\"a.mp4\"}]' \\\n"
               "    --manifest scenes/04_demo/manifest.json --output out.mp4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--scene-dir", required=True, help="Scene directory")
    parser.add_argument("--segments", required=True, help="JSON array of {id, video, transition?}")
    parser.add_argument("--overlays", default="[]", help="JSON array of overlay configs")
    parser.add_argument("--manifest", required=True, help="Path to manifest.json")
    parser.add_argument("--output", required=True, help="Output MP4 path")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    args = parser.parse_args()

    scene_dir = args.scene_dir.rstrip("/")
    scene_name = os.path.basename(scene_dir)
    project_root = get_project_root()
    python = get_python()

    segments = json.loads(args.segments)
    overlays = json.loads(args.overlays)
    output_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(output_dir, exist_ok=True)

    # Build video map from segments
    video_map = {seg["id"]: seg["video"] for seg in segments}

    # Identify foreground segments
    fg_overlay_ids = {o.get("foreground_segment") for o in overlays if o.get("foreground_segment")}

    # ── Overlay processing ────────────────────────────
    if overlays:
        print("[composite-assemble] Processing overlays...")
        for ov in overlays:
            base_id = ov.get("base_segment", "")
            fg_id = ov.get("foreground_segment", "")
            start = ov.get("start", 0)
            duration = ov.get("duration")
            x = ov.get("x", "0")
            y = ov.get("y", "0")
            blend = ov.get("blend", "overlay")

            base_video = video_map.get(base_id)
            fg_video = video_map.get(fg_id)
            overlay_output = os.path.join(output_dir, f"overlay_{base_id}_{fg_id}.mp4")

            if not base_video or not os.path.isfile(base_video):
                print(f"Error: overlay base video not found: {base_video}", file=sys.stderr)
                sys.exit(1)
            if not fg_video or not os.path.isfile(fg_video):
                print(f"Error: overlay foreground video not found: {fg_video}", file=sys.stderr)
                sys.exit(1)

            dur_args = []
            if duration is not None:
                dur_args = ["--duration", str(duration)]

            print(
                f"[composite-assemble] Overlay {fg_id} onto {base_id} "
                f"(blend={blend}, start={start}, x={x}, y={y})"
            )
            cmd = [
                python,
                os.path.join(project_root, "bin", "composite-overlay.py"),
                overlay_output,
                "--base", base_video,
                "--foreground", fg_video,
                "--start", str(start),
                "--x", str(x),
                "--y", str(y),
                "--blend", blend,
            ] + dur_args
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"[composite-assemble] Overlay failed:\n{result.stderr}", file=sys.stderr)
                sys.exit(1)

            # Update video map
            video_map[base_id] = overlay_output
            # Update segment video references
            for seg in segments:
                if seg["id"] == base_id:
                    seg["video"] = overlay_output
                    break

    # Build ordered video list, skipping foreground segments
    ordered_videos = []
    transitions = []
    for seg in segments:
        seg_id = seg["id"]
        if seg_id in fg_overlay_ids:
            continue
        ordered_videos.append(video_map[seg_id])
        trans = seg.get("transition")
        transitions.append(json.dumps(trans) if trans else "")

    # ── Concat / Transition ───────────────────────────
    has_transition = any(t and t != "null" for t in transitions)
    if has_transition:
        print("[composite-assemble] Building transition filtergraph...")
        seg_list = []
        for vid, t in zip(ordered_videos, transitions, strict=False):
            item = {"video": vid}
            if t and t != "null":
                item["transition"] = json.loads(t)
            seg_list.append(item)
        seg_list_json = json.dumps(seg_list)
        result = subprocess.run(
            [
                python,
                os.path.join(project_root, "bin", "composite-transition.py"),
                args.output,
                "--segments", seg_list_json,
            ],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"[composite-assemble] Transition failed:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"[composite-assemble] Concatenating {len(ordered_videos)} segments...")
        cmd = [
            "bash",
            os.path.join(project_root, "pipeline", "concat.sh"),
            args.output,
        ] + ordered_videos
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[composite-assemble] Concat failed:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)

    # ── Audio track composition ───────────────────────
    audio_script = os.path.join(project_root, "bin", "composite-audio.py")
    manifest_has_audio = False
    if os.path.isfile(args.manifest):
        with open(args.manifest, encoding="utf-8") as f:
            manifest_data = json.load(f)
        manifest_has_audio = bool(manifest_data.get("audio"))

    if os.path.isfile(audio_script) and os.access(audio_script, os.X_OK) and manifest_has_audio:
        print("[composite-assemble] Mixing audio tracks...")
        video_only = os.path.join(output_dir, "final_video.mp4")
        os.rename(args.output, video_only)
        result = subprocess.run(
            [python, audio_script, video_only, args.manifest, args.output],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            os.remove(video_only)
        else:
            print("[composite-assemble] Audio mixing failed, keeping video-only output", file=sys.stderr)
            os.rename(video_only, args.output)

    # ── Dependency-graph cache populate ───────────────
    cache_script = os.path.join(project_root, "bin", "composite-cache.py")
    if os.path.isfile(cache_script) and os.access(cache_script, os.X_OK):
        subprocess.run(
            [python, cache_script, "populate", scene_dir, output_dir],
            capture_output=True, text=True, check=False,
        )

    # ── Deliver ───────────────────────────────────────
    tmp_dir = os.path.join(".agent", "tmp", scene_name)
    subprocess.run(
        [python, os.path.join(project_root, "pipeline", "deliver.py"), scene_name, tmp_dir, os.path.join(project_root, "output")],
        capture_output=True, text=True, check=False,
    )

    # ── Output ────────────────────────────────────────
    if args.json:
        final_size = os.path.getsize(args.output) if os.path.isfile(args.output) else 0
        print(
            json.dumps(
                {
                    "scene": scene_name,
                    "type": "composite",
                    "segments": len(segments),
                    "output": args.output,
                    "final_size_bytes": final_size,
                },
                indent=2,
            )
        )
    # Note: "Done" message is printed by the orchestrator (composite-render.py)


if __name__ == "__main__":
    main()
