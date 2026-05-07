#!/usr/bin/env python3
"""bin/check-static.py
基于幕的静态检查，不渲染画面（秒级完成）。

用法:
    check-static.py scenes/04_base_demo/
"""

import ast
import json
import os
import re
import sys
from datetime import datetime, timezone


def fail(msg: str):
    print(msg, file=sys.stderr)
    sys.exit(1)


def find_function_blocks(source_path: str):
    """解析源码，返回 {def_lineno: (start, end, name)}。"""
    with open(source_path, 'r', encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source)
    blocks = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            blocks[node.lineno] = (node.lineno, node.end_lineno, node.name)
    return blocks


def extract_acts_from_source(source_path: str):
    """从 scene.py 提取 @act: 注释（内联实现，保持自包含）。"""
    ACT_RE = re.compile(r'^\s*#\s*@act:(\w+)\s*$')
    TIME_RE = re.compile(r'^\s*#\s*@time:([\d.]+)-([\d.]+)s\s*$')
    KEYFRAMES_RE = re.compile(r'^\s*#\s*@keyframes:\[(.*?)\]\s*$')
    DESC_RE = re.compile(r'^\s*#\s*@description:(.*)$')
    CHECKS_RE = re.compile(r'^\s*#\s*@checks:\[(.*?)\]\s*$')

    acts = []
    current = None

    with open(source_path, 'r', encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            m = ACT_RE.match(line)
            if m:
                if current:
                    current['line_end'] = lineno - 1
                current = {
                    'id': m.group(1),
                    'file': os.path.basename(source_path),
                    'line_start': lineno,
                }
                acts.append(current)
                continue

            if not current:
                continue

            m = TIME_RE.match(line)
            if m:
                current['time_range'] = [float(m.group(1)), float(m.group(2))]
                continue

            m = KEYFRAMES_RE.match(line)
            if m:
                current['keyframes'] = [
                    float(x.strip()) for x in m.group(1).split(',') if x.strip()
                ]
                continue

            m = DESC_RE.match(line)
            if m:
                current['description'] = m.group(1).strip()
                continue

            m = CHECKS_RE.match(line)
            if m:
                current['checks'] = [
                    x.strip().strip('"\'') for x in m.group(1).split(',') if x.strip()
                ]
                continue

            if line.strip() and not line.strip().startswith('#'):
                current['line_end'] = lineno - 1
                current = None

    if current and 'line_end' not in current:
        with open(source_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            current['line_end'] = len(lines)

    return acts


def get_code_block(source_path: str, line_start: int, line_end: int) -> str:
    with open(source_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    return ''.join(lines[line_start - 1:line_end])


def calc_animation_time(code_block: str) -> float:
    """累加 self.wait() 与 run_time 参数得到总动画时间。"""
    total = 0.0

    # self.wait(X)
    for m in re.finditer(r'self\.wait\(([^)]+)\)', code_block):
        expr = m.group(1).strip()
        try:
            total += float(ast.literal_eval(expr))
        except Exception:
            pass

    # self.wait() 无参数 —— manim 默认约 1.0s
    for _ in re.finditer(r'self\.wait\(\s*\)', code_block):
        total += 1.0

    # run_time=X（出现在 self.play、Create、focus_on 等调用中）
    for m in re.finditer(r'run_time\s*=\s*([^,\)\n]+)', code_block):
        expr = m.group(1).strip()
        try:
            total += float(ast.literal_eval(expr))
        except Exception:
            pass

    return total


def count_formulas(code_block: str) -> int:
    return len(re.findall(r'\b(MathTex|Tex|ChineseMathTex)\b', code_block))


def acts_equal(a: dict, b: dict) -> bool:
    keys = ['id', 'time_range', 'keyframes', 'description', 'checks']
    for k in keys:
        if a.get(k) != b.get(k):
            return False
    return True


def main():
    if len(sys.argv) < 2:
        fail("Usage: check-static.py <scene_dir>")

    scene_dir = sys.argv[1]
    if not os.path.isdir(scene_dir):
        fail(f"Error: directory not found: {scene_dir}")

    scene_name = os.path.basename(os.path.normpath(scene_dir))
    manifest_path = os.path.join(scene_dir, 'manifest.json')
    source_path = os.path.join(scene_dir, 'scene.py')

    if not os.path.exists(manifest_path):
        fail(f"Error: manifest.json not found: {manifest_path}")
    if not os.path.exists(source_path):
        fail(f"Error: scene.py not found: {source_path}")

    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    resolution = manifest.get('resolution', [1920, 1080])
    area = resolution[0] * resolution[1]

    func_blocks = find_function_blocks(source_path)
    # 将函数块按 def 行号排序
    sorted_funcs = sorted(func_blocks.values(), key=lambda x: x[0])

    manifest_acts = manifest.get('acts', [])
    extracted_acts = extract_acts_from_source(source_path)

    manifest_by_id = {a['id']: a for a in manifest_acts}
    extracted_by_id = {a['id']: a for a in extracted_acts}
    all_ids = sorted(set(manifest_by_id) | set(extracted_by_id))

    results = []

    for act_id in all_ids:
        m_act = manifest_by_id.get(act_id)
        e_act = extracted_by_id.get(act_id)

        status = 'pass'
        issues = []
        suggested_lines = []

        # c) 代码-注释一致性
        if m_act is None:
            status = 'warning'
            issues.append({
                'type': 'manifest_missing',
                'message': f'Act "{act_id}" 存在于源码注释但不在 manifest.json 中',
                'suggested_lines': [e_act.get('line_start', 0), e_act.get('line_end', 0)] if e_act else [0, 0]
            })
            results.append({'id': act_id, 'status': status, 'issues': issues})
            continue

        if e_act is None:
            status = 'warning'
            issues.append({
                'type': 'source_missing',
                'message': f'Act "{act_id}" 存在于 manifest.json 但不在源码注释中',
                'suggested_lines': [m_act.get('line_start', 0), m_act.get('line_end', 0)]
            })
            results.append({'id': act_id, 'status': status, 'issues': issues})
            continue

        if not acts_equal(m_act, e_act):
            status = 'warning'
            issues.append({
                'type': 'comment_manifest_mismatch',
                'message': f'Act "{act_id}" 的注释与 manifest.json 内容不一致',
                'suggested_lines': [e_act.get('line_start', 0), e_act.get('line_end', 0)]
            })

        # manifest 中的 line_end 通常只到注释末尾；通过 AST 扩展到实际函数体
        block_start = m_act['line_start']
        block_end = m_act['line_end']
        for fs, fe, _fname in sorted_funcs:
            if fs > block_end:
                block_start = fs
                block_end = fe
                break

        code_block = get_code_block(source_path, block_start, block_end)
        suggested_lines = [block_start, block_end]

        # a) 幕时间一致性
        declared_start, declared_end = m_act.get('time_range', [0.0, 0.0])
        declared_duration = declared_end - declared_start
        computed_duration = calc_animation_time(code_block)

        if abs(computed_duration - declared_duration) > 0.5:
            if status == 'pass':
                status = 'warning'
            issues.append({
                'type': 'duration_mismatch',
                'message': (
                    f'声明时长 {declared_duration:.2f}s '
                    f'与计算动画时间 {computed_duration:.2f}s 偏差超过 0.5s'
                ),
                'suggested_lines': suggested_lines
            })

        # b) 公式密度检查
        formula_count = count_formulas(code_block)
        if formula_count > 0:
            pixels_per_formula = area / formula_count
            if pixels_per_formula < 50000:
                if status == 'pass':
                    status = 'warning'
                issues.append({
                    'type': 'formula_density',
                    'message': (
                        f'公式密度过高：{formula_count} 个公式，'
                        f'每公式仅 {pixels_per_formula:.0f} 像素（建议 ≥ 50000）'
                    ),
                    'suggested_lines': suggested_lines
                })

        results.append({'id': act_id, 'status': status, 'issues': issues})

    output = {
        'scene': scene_name,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'acts': results
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
