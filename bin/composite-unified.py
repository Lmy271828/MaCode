#!/usr/bin/env python3
"""bin/composite-unified.py
生成 composite-unified 模式的编排器 scene.py 和 manifest.json。

用法:
    composite-unified.py <composite_scene_dir> <tmp_output_dir>
"""

import argparse
import ast
import json
import os
import re
import sys

_SCRIPT_BIN = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_BIN not in sys.path:
    sys.path.insert(0, _SCRIPT_BIN)
from project_engine import find_project_root, resolve_engine_from_manifest

# Base class names recognised by the AST scanner.
_SCENE_BASE_NAMES = {
    "Scene",
    "MaCodeScene",
    "MovingCameraScene",
    "CameraScene",
    "ThreeDScene",
}


def find_scene_class(source_path: str) -> str:
    """从 scene.py 中提取继承 Scene/MaCodeScene/MovingCameraScene 的类名。

    优先使用 AST 解析继承关系；AST 失败时回退到正则匹配第一行 class 定义。
    """
    try:
        with open(source_path, encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_name = ""
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr
                    if base_name in _SCENE_BASE_NAMES:
                        return node.name
    except Exception:
        pass

    # Fallback to regex
    try:
        with open(source_path, encoding="utf-8") as f:
            for line in f:
                m = re.search(r"^class\s+(\w+)\s*\(", line)
                if m:
                    return m.group(1)
    except Exception:
        pass

    return "Scene"


def load_duration(manifest_path: str) -> float:
    """读取 manifest 的 duration 字段。"""
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    return float(data.get("duration", 0))


def generate_orchestrator(scene_dir: str, output_dir: str) -> dict:
    """
    读取 composite-unified manifest，生成编排器文件。
    返回生成的 manifest 数据字典。
    """
    manifest_path = os.path.join(scene_dir, "manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    segments = manifest.get("segments", [])
    if not segments:
        print("Error: no segments in composite-unified manifest", file=sys.stderr)
        sys.exit(1)

    project_root = find_project_root(scene_dir)
    engine = resolve_engine_from_manifest(manifest, scene_dir, project_root)
    fps = manifest.get("fps", 30)
    resolution = manifest.get("resolution", [1920, 1080])
    params = manifest.get("params")

    # 收集每个 shot 的信息
    shots = []
    total_duration = 0.0
    for i, seg in enumerate(segments):
        seg_id = seg.get("id", f"seg{i}")
        seg_dir = seg.get("scene_dir", "")
        full_dir = os.path.join(scene_dir, seg_dir)
        scene_py = os.path.join(full_dir, "scene.py")
        seg_manifest = os.path.join(full_dir, "manifest.json")

        if not os.path.isfile(scene_py):
            print(f"Error: scene.py not found: {scene_py}", file=sys.stderr)
            sys.exit(1)

        class_name = find_scene_class(scene_py)
        shots.append(
            {
                "id": seg_id,
                "scene_py": scene_py,
                "class_name": class_name,
                "module_name": f"shot_{seg_id}",
            }
        )

        if os.path.isfile(seg_manifest):
            total_duration += load_duration(seg_manifest)

    total_duration = round(total_duration, 2)

    os.makedirs(output_dir, exist_ok=True)

    # ── 生成 orchestrator scene.py ──
    lines = []
    lines.append('"""Auto-generated orchestrator for composite-unified scene."""')
    lines.append("")
    lines.append("import importlib.util")
    lines.append("import json")
    lines.append("import os")
    lines.append("import sys")
    lines.append("")

    # 参数注入
    if params is not None:
        lines.append("# ── Composite params injection ──")
        lines.append("_params = {}")
        lines.append('_params_file = os.environ.get("MACODE_PARAMS_JSON", "")')
        lines.append("if _params_file and os.path.isfile(_params_file):")
        lines.append("    with open(_params_file) as f:")
        lines.append("        _params = json.load(f)")
        lines.append("")

    lines.append("from templates.scene_base import MaCodeScene")
    if engine == "manimgl":
        lines.append("from manimlib import *")
    else:
        lines.append("from manim import *")
    lines.append("")

    # 动态加载各 shot 模块
    for shot in shots:
        mod = shot["module_name"]
        path = shot["scene_py"]
        lines.append(f"# Load shot: {shot['id']}")
        lines.append(f'spec_{mod} = importlib.util.spec_from_file_location("{mod}", "{path}")')
        lines.append(f"{mod} = importlib.util.module_from_spec(spec_{mod})")
        lines.append(f"spec_{mod}.loader.exec_module({mod})")
        lines.append("")

    lines.append("")
    lines.append("class CompositeUnifiedScene(MaCodeScene):")
    lines.append('    """Auto-generated unified composite scene."""')
    lines.append("")
    lines.append("    def construct(self):")

    for shot in shots:
        mod = shot["module_name"]
        cls = shot["class_name"]
        lines.append(f"        # Segment: {shot['id']}")
        lines.append(f"        {mod}.{cls}.construct(self)")
        lines.append("")

    orchestrator_path = os.path.join(output_dir, "scene.py")
    with open(orchestrator_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # ── 生成标准 manifest.json ──
    output_manifest = {
        "engine": engine,
        "duration": total_duration,
        "fps": fps,
        "resolution": resolution,
        "assets": [],
        "dependencies": [],
        "meta": {
            "title": manifest.get("meta", {}).get("title", "Composite Unified"),
            "type": "composite-unified-generated",
        },
    }

    manifest_path = os.path.join(output_dir, "manifest.json")
    raw = json.dumps(output_manifest, indent=2, ensure_ascii=False)
    # 把 resolution 的多行格式压缩为单行（兼容 validate_manifest 的 sed 正则）
    raw = re.sub(r'"resolution": \[\s*(\d+),\s*(\d+)\s*\]', r'"resolution": [\1, \2]', raw)
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(raw)
        f.write("\n")

    print(f"[unified] Orchestrator generated: {orchestrator_path}")
    print(f"[unified] Manifest generated: {manifest_path}")
    print(f"[unified] Segments: {len(shots)}, Total duration: {total_duration:.1f}s")

    return output_manifest


def main():
    parser = argparse.ArgumentParser(
        description="Generate composite-unified orchestrator scene.py and manifest.json.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("scene_dir", help="Path to composite-unified scene directory")
    parser.add_argument("tmp_output_dir", help="Temporary output directory for generated files")
    args = parser.parse_args()

    scene_dir = args.scene_dir
    output_dir = args.tmp_output_dir
    generate_orchestrator(scene_dir, output_dir)


if __name__ == "__main__":
    main()
