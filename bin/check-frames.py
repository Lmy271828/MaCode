#!/usr/bin/env python3
"""bin/check-frames.py
基于幕 keyframes 的采样帧检查。

用法:
    check-frames.py scenes/04_base_demo/
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFilter


def fail(msg: str):
    print(msg, file=sys.stderr)
    sys.exit(1)


def find_frame(scene_tmp_dir: str, frame_num: int):
    """在预渲染帧目录中查找对应帧（1-indexed）。"""
    frames_dir = os.path.join(scene_tmp_dir, 'frames')
    candidates = [
        os.path.join(frames_dir, f'frame_{frame_num:04d}.png'),
        os.path.join(frames_dir, f'frame_{frame_num:05d}.png'),
        os.path.join(frames_dir, f'{frame_num:04d}.png'),
        os.path.join(frames_dir, f'{frame_num:05d}.png'),
        os.path.join(frames_dir, f'frame_{frame_num}.png'),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def extract_frame_from_mp4(mp4_path: str, time_sec: float, output_path: str) -> bool:
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-ss', str(time_sec),
        '-i', mp4_path,
        '-vframes', '1',
        '-q:v', '2',
        output_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def check_no_overlap(img: Image.Image):
    """简化重叠检测：灰度 → 前景提取（二值化）→ 连通块 → 边界框 IOU。

    manim 默认黑底彩字/图形，阈值 20 可把物体从背景中分离。
    """
    gray = img.convert('L')
    # 前景：非黑像素；膨胀以连接同一物体的抗锯齿断裂
    foreground = gray.point(lambda p: 255 if p > 20 else 0)
    dilated = foreground.filter(ImageFilter.MaxFilter(3))
    # 缩小加速连通块分析
    small = dilated.resize((dilated.width // 4, dilated.height // 4))
    pixels = small.load()
    visited = set()
    boxes = []

    def flood_fill(sx: int, sy: int):
        stack = [(sx, sy)]
        minx, miny, maxx, maxy = sx, sy, sx, sy
        while stack:
            x, y = stack.pop()
            if x < 0 or x >= small.width or y < 0 or y >= small.height:
                continue
            if (x, y) in visited:
                continue
            if pixels[x, y] == 0:
                continue
            visited.add((x, y))
            minx, miny = min(minx, x), min(miny, y)
            maxx, maxy = max(maxx, x), max(maxy, y)
            stack.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])
        return minx, miny, maxx, maxy

    for y in range(small.height):
        for x in range(small.width):
            if pixels[x, y] != 0 and (x, y) not in visited:
                bx = flood_fill(x, y)
                bw = bx[2] - bx[0] + 1
                bh = bx[3] - bx[1] + 1
                # 过滤细小噪声
                if bw > 5 and bh > 5:
                    boxes.append(bx)

    # 还原到原图坐标
    full_boxes = [
        (x * 4, y * 4, (x2 + 1) * 4, (y2 + 1) * 4)
        for x, y, x2, y2 in boxes
    ]

    def iou(a, b):
        ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
        iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
        inter = ix * iy
        if inter == 0:
            return 0.0
        area_a = (a[2] - a[0]) * (a[3] - a[1])
        area_b = (b[2] - b[0]) * (b[3] - b[1])
        # 使用较小面积作为分母，更敏感地检测小物体被大物体覆盖
        return inter / min(area_a, area_b)

    overlaps = []
    for i in range(len(full_boxes)):
        for j in range(i + 1, len(full_boxes)):
            if iou(full_boxes[i], full_boxes[j]) > 0.1:
                overlaps.append((full_boxes[i], full_boxes[j]))
    return overlaps


def check_formula_readable(img: Image.Image):
    gray = img.convert('L')
    hist = gray.histogram()
    total = sum(hist)
    if total == 0:
        return True, 0.5
    dark_ratio = sum(hist[:64]) / total
    bright_ratio = sum(hist[-64:]) / total
    if dark_ratio > 0.85 or bright_ratio > 0.95:
        return False, dark_ratio
    return True, dark_ratio


def check_camera_focused(_img: Image.Image):
    """简化实现：留作扩展，暂时总是 pass。"""
    return True, None


def annotate_image(img: Image.Image, overlaps, check_name: str) -> Image.Image:
    draw = ImageDraw.Draw(img)
    if overlaps and check_name == 'no_overlap':
        for a, b in overlaps:
            draw.rectangle(a, outline='red', width=4)
            draw.rectangle(b, outline='red', width=4)
    return img


def main():
    if len(sys.argv) < 2:
        fail("Usage: check-frames.py <scene_dir>")

    scene_dir = sys.argv[1]
    if not os.path.isdir(scene_dir):
        fail(f"Error: directory not found: {scene_dir}")

    scene_name = os.path.basename(os.path.normpath(scene_dir))
    manifest_path = os.path.join(scene_dir, 'manifest.json')

    if not os.path.exists(manifest_path):
        fail(f"Error: manifest.json not found: {manifest_path}")

    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    fps = manifest.get('fps', 30)
    acts = manifest.get('acts', [])

    scene_tmp_dir = os.path.join('.agent', 'tmp', scene_name)
    check_frames_dir = os.path.join(scene_tmp_dir, 'check_frames')
    os.makedirs(check_frames_dir, exist_ok=True)

    results = []

    for act in acts:
        act_id = act['id']
        keyframes = act.get('keyframes', [])
        checks = act.get('checks', [])
        line_start = act.get('line_start', 0)
        line_end = act.get('line_end', 0)
        suggested_lines = [line_start, line_end] if line_start and line_end else []

        status = 'pass'
        issues = []
        keyframes_checked = 0

        for kf in keyframes:
            frame_num = int(kf * fps) + 1  # 1-indexed
            frame_path = find_frame(scene_tmp_dir, frame_num)
            annotated_path = os.path.join(check_frames_dir, f'{act_id}_{kf}.png')

            if frame_path is None:
                mp4_path = os.path.join(scene_tmp_dir, 'raw.mp4')
                if os.path.exists(mp4_path):
                    temp_path = os.path.join(check_frames_dir, f'_tmp_{act_id}_{kf}.png')
                    if extract_frame_from_mp4(mp4_path, kf, temp_path):
                        frame_path = temp_path
                    else:
                        if status == 'pass':
                            status = 'warning'
                        issues.append({
                            'type': 'frame_missing',
                            'time': kf,
                            'frame': None,
                            'message': f'无法从 raw.mp4 截取时间点 {kf}s 的帧',
                            'suggested_lines': suggested_lines,
                            'suggested_fix': '检查视频文件或重新渲染',
                        })
                        continue
                else:
                    if status == 'pass':
                        status = 'warning'
                    issues.append({
                        'type': 'frame_missing',
                        'time': kf,
                        'frame': None,
                        'message': f'找不到帧号 {frame_num}（时间 {kf}s），且 raw.mp4 不存在',
                        'suggested_lines': suggested_lines,
                        'suggested_fix': '先渲染场景生成帧或视频',
                    })
                    continue

            keyframes_checked += 1

            try:
                img = Image.open(frame_path)
            except Exception as e:
                if status == 'pass':
                    status = 'warning'
                issues.append({
                    'type': 'frame_error',
                    'time': kf,
                    'frame': frame_path,
                    'message': f'无法打开帧图像: {e}',
                    'suggested_lines': suggested_lines,
                    'suggested_fix': '检查帧文件是否损坏',
                })
                continue

            overlaps = []
            annotated = False

            if 'no_overlap' in checks:
                overlaps = check_no_overlap(img)
                if overlaps:
                    if status == 'pass':
                        status = 'warning'
                    issues.append({
                        'type': 'overlap',
                        'time': kf,
                        'frame': annotated_path,
                        'message': '检测到元素重叠',
                        'suggested_lines': suggested_lines,
                        'suggested_fix': '增大 buff 参数或调整位置',
                    })
                    img = annotate_image(img, overlaps, 'no_overlap')
                    annotated = True

            if 'formula_readable' in checks:
                readable, dark_ratio = check_formula_readable(img)
                if not readable:
                    if status == 'pass':
                        status = 'warning'
                    issues.append({
                        'type': 'formula_unreadable',
                        'time': kf,
                        'frame': annotated_path,
                        'message': f'画面过暗或过亮，暗区占比 {dark_ratio:.2%}，可能影响公式可读性',
                        'suggested_lines': suggested_lines,
                        'suggested_fix': '调整背景亮度或公式颜色对比度',
                    })
                    annotated = True

            if 'camera_focused' in checks:
                focused, _ = check_camera_focused(img)
                if not focused:
                    if status == 'pass':
                        status = 'warning'
                    issues.append({
                        'type': 'camera_unfocused',
                        'time': kf,
                        'frame': annotated_path,
                        'message': '相机未聚焦（简化检查占位）',
                        'suggested_lines': suggested_lines,
                        'suggested_fix': '检查 focus_on 调用',
                    })
                    annotated = True

            # 保存带标注的采样帧（无论是否有问题，均保留以便人工复核）
            img.save(annotated_path)
            # 把 frame 路径更新为标注图路径
            for issue in issues:
                if issue.get('time') == kf and issue.get('frame') is None:
                    issue['frame'] = annotated_path

        results.append({
            'id': act_id,
            'status': status,
            'keyframes_checked': keyframes_checked,
            'issues': issues,
        })

    output = {
        'scene': scene_name,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'acts': results,
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
