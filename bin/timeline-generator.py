#!/usr/bin/env python3
"""bin/timeline-generator.py
生成项目级时间轴 HTML（甘特图风格）。

用法:
    timeline-generator.py
输出:
    .agent/reports/timeline.html
"""

import json
import os
import glob


def collect_scenes():
    """遍历所有场景，收集 manifest 中的 acts 和 duration。"""
    scenes = []
    for manifest_path in sorted(glob.glob("scenes/*/manifest.json")):
        scene_dir = os.path.dirname(manifest_path)
        scene_name = os.path.basename(scene_dir)
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        acts = data.get("acts", [])
        duration = data.get("duration", 0)
        if not duration and acts:
            duration = acts[-1].get("time_range", [0, 0])[-1]
        engine = data.get("engine", "unknown")
        title = data.get("meta", {}).get("title", scene_name)

        scenes.append({
            "name": scene_name,
            "title": title,
            "engine": engine,
            "duration": duration,
            "acts": acts,
        })
    return scenes


def generate_html():
    scenes = collect_scenes()
    if not scenes:
        print("No scenes found.", file=sys.stderr)
        return

    max_duration = max(s["duration"] for s in scenes) if scenes else 1
    if max_duration <= 0:
        max_duration = 1

    # 为每幕分配颜色
    colors = [
        "#4ecca3", "#f4d03f", "#e74c3c", "#3498db",
        "#9b59b6", "#1abc9c", "#e67e22", "#2ecc71",
    ]

    def act_color(idx):
        return colors[idx % len(colors)]

    html_parts = []
    html_parts.append(f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>MaCode Project Timeline</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; background: #1a1a2e; color: #eee; }}
  h1 {{ font-weight: 300; letter-spacing: 1px; }}
  .timeline {{ margin-top: 30px; }}
  .track {{ display: flex; align-items: center; margin: 12px 0; min-height: 48px; }}
  .track-label {{ width: 220px; flex-shrink: 0; padding-right: 16px; text-align: right; }}
  .track-label .name {{ font-size: 14px; font-weight: 500; color: #eee; }}
  .track-label .meta {{ font-size: 11px; color: #a0a0c0; margin-top: 2px; }}
  .track-bar {{ flex: 1; position: relative; height: 36px; background: #0f0f23; border-radius: 4px; overflow: hidden; display: flex; }}
  .segment {{ height: 100%; display: flex; align-items: center; justify-content: center; font-size: 11px; color: #1a1a2e; font-weight: 600; position: relative; cursor: default; transition: filter 0.15s; }}
  .segment:hover {{ filter: brightness(1.2); z-index: 2; }}
  .segment .tooltip {{ position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); margin-bottom: 6px; padding: 6px 10px; background: #222; color: #eee; font-size: 11px; white-space: nowrap; border-radius: 4px; opacity: 0; pointer-events: none; transition: opacity 0.15s; z-index: 10; }}
  .segment:hover .tooltip {{ opacity: 1; }}
  .axis {{ display: flex; align-items: center; margin: 20px 0 10px 236px; position: relative; height: 24px; }}
  .tick {{ position: absolute; top: 0; font-size: 11px; color: #a0a0c0; transform: translateX(-50%); }}
  .tick::before {{ content: ""; position: absolute; top: 16px; left: 50%; width: 1px; height: 8px; background: #444; }}
  .legend {{ margin-top: 30px; font-size: 12px; color: #a0a0c0; }}
</style>
</head>
<body>
  <h1>🎬 MaCode Project Timeline</h1>
  <p style="color:#a0a0c0;">Total scenes: {len(scenes)} | Max duration: {max_duration:.1f}s</p>
  <div class="timeline">
""")

    # 时间轴刻度
    html_parts.append('    <div class="axis">\n')
    ticks = 10
    for i in range(ticks + 1):
        pos = (i / ticks) * 100
        val = (i / ticks) * max_duration
        html_parts.append(f'      <div class="tick" style="left:{pos:.1f}%">{val:.1f}s</div>\n')
    html_parts.append('    </div>\n')

    for scene in scenes:
        name = scene["name"]
        title = scene["title"]
        engine = scene["engine"]
        duration = scene["duration"]
        acts = scene["acts"]

        html_parts.append(f"""    <div class="track">
      <div class="track-label">
        <div class="name">{name}</div>
        <div class="meta">{title} | {engine} | {duration:.1f}s</div>
      </div>
      <div class="track-bar">
""")
        if acts:
            for idx, act in enumerate(acts):
                tr = act.get("time_range", [0, 0])
                t0, t1 = tr[0], tr[1] if len(tr) > 1 else tr[0]
                seg_dur = t1 - t0
                left_pct = (t0 / max_duration) * 100
                width_pct = (seg_dur / max_duration) * 100
                color = act_color(idx)
                aid = act.get("id", f"act{idx}")
                desc = act.get("description", "")
                tooltip = f"{aid}: {t0}-{t1}s"
                if desc:
                    tooltip += f" — {desc}"
                html_parts.append(f"""        <div class="segment" style="margin-left:{left_pct:.2f}%;width:{width_pct:.2f}%;background:{color};">
          <span>{aid}</span>
          <div class="tooltip">{tooltip}</div>
        </div>
""")
        else:
            # 没有 acts，只显示一条总时长条
            width_pct = (duration / max_duration) * 100
            html_parts.append(f"""        <div class="segment" style="margin-left:0%;width:{width_pct:.2f}%;background:#555;">
          <span>scene</span>
          <div class="tooltip">{name}: 0-{duration}s</div>
        </div>
""")

        html_parts.append("""      </div>
    </div>
""")

    html_parts.append("""  </div>
  <div class="legend">
    <p>Each row represents a scene. Colored segments are acts. Hover for details.</p>
  </div>
</body>
</html>
""")

    out_dir = ".agent/reports"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "timeline.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("".join(html_parts))
    print(f"Timeline generated: {out_path}")


if __name__ == "__main__":
    generate_html()
