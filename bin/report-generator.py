#!/usr/bin/env python3
"""bin/report-generator.py
生成场景级 HTML 报告（幕画廊）。

用法:
    report-generator.py scenes/04_base_demo/
"""

import json
import os
import sys
import glob


def load_acts(scene_dir):
    """从 manifest.json 或 acts.json 读取 acts。"""
    manifest_path = os.path.join(scene_dir, "manifest.json")
    acts_path = os.path.join(scene_dir, "acts.json")

    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "acts" in data:
            return data["acts"], data
    if os.path.exists(acts_path):
        with open(acts_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("acts", []), data
    return [], {}


def load_check_reports(scene_name):
    """加载该场景的所有 check 报告。"""
    reports_dir = ".agent/check_reports"
    pattern = os.path.join(reports_dir, f"{scene_name}_*.json")
    reports = []
    for path in glob.glob(pattern):
        with open(path, "r", encoding="utf-8") as f:
            try:
                reports.append(json.load(f))
            except json.JSONDecodeError:
                continue
    return reports


def build_issue_map(reports):
    """将 check 报告中的 issues 按 act_id 聚合。"""
    act_issues = {}
    for report in reports:
        for act in report.get("acts", []):
            aid = act["id"]
            if aid not in act_issues:
                act_issues[aid] = {"status": act.get("status", "pass"), "issues": []}
            act_issues[aid]["issues"].extend(act.get("issues", []))
            # 提升状态优先级: error > warning > pass
            status_order = {"error": 3, "warning": 2, "pass": 1}
            old = act_issues[aid]["status"]
            new = act.get("status", "pass")
            if status_order.get(new, 0) > status_order.get(old, 0):
                act_issues[aid]["status"] = new
    return act_issues


def find_frame_path(scene_name, act_id, time_val, fps=30):
    """查找某一幕某时刻的帧图片路径，返回相对于报告 HTML 的相对路径。"""
    # 优先 check_frames 目录（按 act_id 和时间命名）
    check_frames_dir = f".agent/tmp/{scene_name}/check_frames"
    if os.path.isdir(check_frames_dir):
        # 尝试精确匹配，如 intro_0.0.png, intro_0.80.png 等
        candidates = [
            f"{act_id}_{time_val:g}.png",
            f"{act_id}_{time_val:.1f}.png",
            f"{act_id}_{time_val:.2f}.png",
        ]
        for cand in candidates:
            p = os.path.join(check_frames_dir, cand)
            if os.path.exists(p):
                return f"../../tmp/{scene_name}/check_frames/{cand}"
        # 模糊匹配前缀
        prefix = f"{act_id}_"
        for fname in sorted(os.listdir(check_frames_dir)):
            if fname.startswith(prefix) and fname.endswith(".png"):
                # 从文件名提取时间
                try:
                    t_str = fname[len(prefix):-4]
                    t = float(t_str)
                    if abs(t - time_val) < 0.001:
                        return f"../../tmp/{scene_name}/check_frames/{fname}"
                except ValueError:
                    pass

    # 回退到 frames 目录（按帧号命名）
    frames_dir = f".agent/tmp/{scene_name}/frames"
    if os.path.isdir(frames_dir):
        frame_idx = int(time_val * fps) + 1
        fname = f"frame_{frame_idx:04d}.png"
        if os.path.exists(os.path.join(frames_dir, fname)):
            return f"../../tmp/{scene_name}/frames/{fname}"

    return None


def escape_html(text):
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def generate_html(scene_dir):
    scene_dir = scene_dir.rstrip("/")
    scene_name = os.path.basename(scene_dir)

    acts, manifest = load_acts(scene_dir)
    if not acts:
        print(f"No acts found for {scene_name}", file=sys.stderr)
        sys.exit(1)

    duration = manifest.get("duration", 0)
    if not duration and acts:
        duration = acts[-1].get("time_range", [0, 0])[-1]

    fps = manifest.get("fps", 30)
    reports = load_check_reports(scene_name)
    issue_map = build_issue_map(reports)

    # 确保输出目录存在
    out_dir = f".agent/reports/{scene_name}"
    os.makedirs(out_dir, exist_ok=True)

    # 收集帧状态
    def frame_status(aid, time_val):
        info = issue_map.get(aid, {})
        for issue in info.get("issues", []):
            t = issue.get("time")
            if t is not None and abs(t - time_val) < 0.001:
                return issue.get("type", "warning")
        if info.get("status") == "error":
            return "error"
        if info.get("status") == "warning":
            return "warning"
        return "pass"

    html_parts = []
    html_parts.append(f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Scene Report: {escape_html(scene_name)}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; background: #1a1a2e; color: #eee; }}
  h1 {{ font-weight: 300; letter-spacing: 1px; }}
  .meta {{ color: #a0a0c0; margin-bottom: 30px; }}
  .act {{ margin: 30px 0; padding: 20px; background: #16213e; border-radius: 8px; border-left: 4px solid #0f3460; }}
  .act-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
  .act-header h3 {{ margin: 0; font-weight: 400; }}
  .status {{ font-weight: 600; font-size: 14px; }}
  .status-pass {{ color: #4ecca3; }}
  .status-warning {{ color: #f4d03f; }}
  .status-error {{ color: #e74c3c; }}
  .description {{ color: #c0c0d0; margin: 8px 0; }}
  .code-ref {{ color: #a0a0c0; font-size: 13px; margin: 8px 0; }}
  .frames {{ display: flex; gap: 14px; margin: 15px 0; flex-wrap: wrap; }}
  .frame {{ position: relative; text-align: center; }}
  .frame img {{ width: 240px; border-radius: 4px; border: 2px solid #333; display: block; }}
  .frame img.warning {{ border-color: #f4d03f; }}
  .frame img.error {{ border-color: #e74c3c; }}
  .frame .label {{ display: block; margin-top: 6px; font-size: 12px; color: #a0a0c0; }}
  .placeholder {{ width: 240px; height: 135px; background: #0f0f23; border: 2px dashed #333; border-radius: 4px; display: flex; align-items: center; justify-content: center; color: #666; font-size: 12px; }}
  .issue-list {{ margin-top: 10px; padding: 10px; background: #0f0f23; border-radius: 4px; }}
  .issue {{ font-size: 13px; margin: 4px 0; }}
  .issue.warning {{ color: #f4d03f; }}
  .issue.error {{ color: #e74c3c; }}
  .code-snippet {{ background: #0f0f23; padding: 15px; border-radius: 4px; overflow-x: auto; margin-top: 12px; }}
  .code-snippet pre {{ margin: 0; color: #a8d8ea; font-size: 12px; }}
</style>
</head>
<body>
  <h1>📽 Scene Report: {escape_html(scene_name)}</h1>
  <p class="meta">Total acts: {len(acts)} | Duration: {duration}s | Engine: {escape_html(manifest.get('engine', 'unknown'))}</p>
""")

    # 尝试读取源码以便展示代码片段
    source_file = acts[0].get("file", "scene.py") if acts else "scene.py"
    source_path = os.path.join(scene_dir, source_file)
    source_lines = []
    if os.path.exists(source_path):
        with open(source_path, "r", encoding="utf-8") as f:
            source_lines = f.readlines()

    for act in acts:
        aid = act["id"]
        time_range = act.get("time_range", [0, 0])
        t_start, t_end = time_range[0], time_range[1] if len(time_range) > 1 else time_range[0]
        keyframes = act.get("keyframes", [t_start, t_end])
        description = act.get("description", "")
        line_start = act.get("line_start", 0)
        line_end = act.get("line_end", 0)

        info = issue_map.get(aid, {})
        status = info.get("status", "pass")
        status_class = f"status-{status}"
        status_icon = "✓ PASS" if status == "pass" else ("⚠ WARNING" if status == "warning" else "✗ ERROR")

        html_parts.append(f"""  <div class="act">
    <div class="act-header">
      <h3>{escape_html(aid)} ({t_start}-{t_end}s)</h3>
      <span class="status {status_class}">{status_icon}</span>
    </div>
    <p class="description">{escape_html(description)}</p>
    <p class="code-ref">Code: {escape_html(source_file)} L{line_start}-L{line_end}</p>
""")

        # 帧
        html_parts.append('    <div class="frames">\n')
        for t in keyframes:
            fpath = find_frame_path(scene_name, aid, t, fps)
            st = frame_status(aid, t)
            img_class = "warning" if st == "warning" else ("error" if st == "error" else "")
            if fpath:
                html_parts.append(f"""      <div class="frame"><img src="{escape_html(fpath)}" class="{img_class}"><span class="label">{t}s</span></div>
""")
            else:
                html_parts.append(f"""      <div class="frame"><div class="placeholder">Frame not rendered yet</div><span class="label">{t}s</span></div>
""")
        html_parts.append('    </div>\n')

        # issues 列表
        issues = info.get("issues", [])
        if issues:
            html_parts.append('    <div class="issue-list">\n')
            for issue in issues:
                itype = issue.get("type", "warning")
                msg = issue.get("message", str(issue))
                html_parts.append(f"""      <div class="issue {itype}">[{itype.upper()}] {escape_html(msg)}</div>
""")
            html_parts.append('    </div>\n')

        # 代码片段
        if source_lines and line_start > 0 and line_end >= line_start:
            snippet = "".join(source_lines[line_start - 1:line_end])
            html_parts.append(f"""    <div class="code-snippet"><pre>{escape_html(snippet)}</pre></div>
""")

        html_parts.append("  </div>\n")

    html_parts.append("""</body>
</html>
""")

    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("".join(html_parts))
    print(f"Report generated: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: report-generator.py <scene_dir/>", file=sys.stderr)
        sys.exit(1)
    generate_html(sys.argv[1])
