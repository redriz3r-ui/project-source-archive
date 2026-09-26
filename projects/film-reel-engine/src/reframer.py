from __future__ import annotations
import math
from statistics import median


def crop_track(shot: dict, edit: dict, ratio: float, source_ratio: float, cfg: dict) -> tuple[str, list[dict]]:
    mode = edit.get('crop_mode', 'auto')
    crop_w = min(1.0, ratio / source_ratio)
    crop_h = min(1.0, source_ratio / ratio)
    settings = cfg['reframing']
    tracks = shot.get('tracking', [])
    start, end = edit['source_in'], edit['source_in'] + edit['duration']
    tracks = [t for t in tracks if start <= t['time'] <= end] or (
        [min(tracks, key=lambda t: abs(t['time'] - (start + end) / 2))] if tracks else [])
    face_centers = []
    for sample in tracks:
        if sample['faces']:
            box = max(sample['faces'], key=lambda f: f[2] * f[3])
            face_centers.append([box[0] + box[2] / 2, box[1] + box[3] / 2])
    unstable = bool(tracks) and max(t['center'][0] for t in tracks) - min(t['center'][0] for t in tracks) > 0.25
    # Preserve multi-person compositions when one crop cannot contain their faces.
    compromised = False
    for sample in tracks:
        faces = sample['faces']
        if len(faces) >= 2:
            span = max(f[0] + f[2] for f in faces) - min(f[0] for f in faces)
            compromised |= span > crop_w * 0.9
        if any(f[2] > crop_w * 0.85 or f[3] > crop_h * 0.85 for f in faces):
            compromised = True
    if mode == 'auto':
        mode = 'blur_background' if compromised or (not face_centers and crop_w < 0.4 and (unstable or shot['motion_score'] < 0.08)) else 'smart_crop'
    if face_centers:
        initial = [median(c[i] for c in face_centers) for i in range(2)]
    elif tracks:
        initial = [median(t['center'][i] for t in tracks[:3]) for i in range(2)]
    else:
        initial = shot['primary_subject']
    center = list(edit.get('crop_center', initial))
    clamp = lambda p: [max(crop_w / 2, min(1 - crop_w / 2, p[0])), max(crop_h / 2, min(1 - crop_h / 2, p[1]))]
    center = clamp(center)
    points = [{'time': 0.0, 'center': center.copy()}]
    if 'crop_center' not in edit:
        for sample in tracks:
            t = max(0, min(edit['duration'], sample['time'] - start))
            dt = t - points[-1]['time']
            if dt <= 0:
                continue
            if face_centers and not sample['faces']:
                target = center.copy()
            elif sample['faces']:
                box = max(sample['faces'], key=lambda f: f[2] * f[3])
                target = clamp([box[0] + box[2] / 2, box[1] + box[3] / 2])
            else:
                target = clamp(sample['center'])
            alpha = 1 - settings['smoothing'] ** (dt * 2)
            delta = [(target[i] - center[i]) * alpha if abs(target[i] - center[i]) > settings['dead_zone'] else 0 for i in range(2)]
            distance = math.hypot(*delta)
            limit = settings['max_pan_speed'] * dt
            if distance > limit:
                delta = [v * limit / distance for v in delta]
            center = clamp([center[i] + delta[i] for i in range(2)])
            points.append({'time': t, 'center': center.copy()})
    return mode, points


def expression(points: list[dict], axis: int) -> str:
    # A sum of clamped linear ramps gives continuous motion, with no nested-if depth limit.
    output = f"{points[0]['center'][axis]:.7f}"
    for before, after in zip(points, points[1:]):
        delta = after['center'][axis] - before['center'][axis]
        if abs(delta) > 1e-7:
            output += f"+({delta:.7f})*clip((t-{before['time']:.6f})/{after['time']-before['time']:.6f},0,1)"
    return output


def filter_graph(mode: str, points: list[dict], width: int, height: int, fps: int) -> str:
    ratio = width / height
    prefix = f'[0:v]setpts=PTS-STARTPTS,scale=trunc(iw*sar/2)*2:ih,setsar=1,fps={fps}'
    if mode == 'smart_crop':
        x, y = expression(points, 0), expression(points, 1)
        return (prefix + f",crop=w='trunc(min(iw,ih*{ratio})/2)*2':h='trunc(min(ih,iw/{ratio})/2)*2':"
                f"x='max(0,min(iw-ow,iw*({x})-ow/2))':y='max(0,min(ih-oh,ih*({y})-oh/2))',"
                f'scale={width}:{height},setsar=1,format=yuv420p[v]')
    if mode in ('fit', 'letterbox'):
        return prefix + f',scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p[v]'
    return (prefix + f',split=2[bg][fg];[bg]scale={width}:{height}:force_original_aspect_ratio=increase,'
            f'crop={width}:{height},boxblur=20:2[blur];[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[front];'
            '[blur][front]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p[v]')
