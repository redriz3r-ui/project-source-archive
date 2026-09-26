from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import cv2
import numpy as np
from .face_detection import FaceDetector
from .frame_analysis import measure
from .motion_analysis import gray_small, motion
from .scene_detection import detect
from .semantic import describe
from .thumbnails import contact_sheets
from .utils import LOG, read_json, signature, validate_source, write_json


def shot_key(film: dict, shot: dict, cfg: dict) -> str:
    return signature({'proxy': film['proxy_key'], 'start': shot['start'], 'end': shot['end'],
                      'sample_fps': cfg['analysis']['sample_fps'],
                      'max_samples': cfg['analysis']['max_samples_per_shot'],
                      'version': cfg['analysis']['algorithm_version'],
                      'face_weight': cfg['reframing']['face_weight']})


def analyze_one(project: Path, film: dict, shot: dict, cfg: dict, key: str) -> dict:
    key = shot_key(film, shot, cfg)
    cache = project / 'analysis/shot_cache' / f'{key}.json'
    if cache.exists():
        saved = read_json(cache)
        if saved.get('cache_key') == key and (project / saved['thumbnail']).exists():
            saved.update(shot)
            return saved
    cap = cv2.VideoCapture(film['proxy'])
    detector = FaceDetector()
    count = max(3, min(int(cfg['analysis']['max_samples_per_shot']), int(shot['duration'] * cfg['analysis']['sample_fps']) + 1))
    margin = min(0.12, shot['duration'] / 8)
    times = np.linspace(shot['start'] + margin, shot['end'] - margin, count)
    features, tracks, flows = [], [], []
    previous = None
    thumbnail = project / 'analysis/frames' / f'shot_{key[:20]}.jpg'
    try:
        for i, stamp in enumerate(times):
            cap.set(cv2.CAP_PROP_POS_MSEC, float(stamp * 1000))
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(f"Cannot decode shot {shot['shot_id']} at {stamp:.2f}s")
            visual = measure(frame)
            faces = detector.detect(frame)
            gray = gray_small(frame)
            movement = motion(previous, gray, float(times[1] - times[0]))
            previous = gray
            subject = movement['subject']
            if faces:
                largest = max(faces, key=lambda f: f[2] * f[3])
                face_center = [largest[0] + largest[2] / 2, largest[1] + largest[3] / 2]
                weight = cfg['reframing']['face_weight']
                subject = [weight * a + (1 - weight) * b for a, b in zip(face_center, subject)]
            tracks.append({'time': float(stamp - shot['start']), 'center': subject, 'faces': faces})
            features.append(visual)
            flows.append(movement)
            if i == count // 2:
                if not cv2.imwrite(str(thumbnail), frame):
                    raise RuntimeError(f'Cannot save thumbnail {thumbnail}')
    finally:
        cap.release()
    result = dict(shot)
    for field in ('brightness', 'contrast', 'saturation', 'entropy', 'edge_density', 'darkness', 'colorfulness'):
        result[field] = float(np.mean([f[field] for f in features]))
    for field in ('motion_score', 'residual_motion', 'visual_change'):
        result[field] = float(np.mean([f[field] for f in flows[1:]]))
    result['mean_color'] = np.mean([f['mean_color'] for f in features], axis=0).tolist()
    result['dominant_colors'] = features[count // 2]['dominant_colors']
    result['faces'] = max(len(t['faces']) for t in tracks)
    result['face_fraction'] = sum(bool(t['faces']) for t in tracks) / count
    result['primary_subject'] = np.median([t['center'] for t in tracks], axis=0).tolist()
    result['tracking'] = tracks
    x, y = result['primary_subject']
    result['composition_score'] = float(1 - min(abs(x - 1/3), abs(x - 2/3)) * 1.4)
    result['visual_interest'] = float(0.35 * result['entropy'] + 0.25 * result['colorfulness'] + 0.2 * min(1, result['contrast'] * 2) + 0.2 * result['face_fraction'])
    camera_speed = float(np.linalg.norm(np.mean([f['camera_flow'] for f in flows[1:]], axis=0)))
    result['camera_motion'] = 'static' if camera_speed < 0.5 else ('handheld-like' if result['residual_motion'] > 0.25 else 'pan-like')
    result['stability'] = 1 - result['residual_motion']
    result['attributes'] = ['dark' if result['brightness'] < 0.3 else 'bright',
                            'high-motion' if result['motion_score'] > 0.35 else 'low-motion',
                            'face-focused' if result['face_fraction'] >= 0.5 else 'environment-focused']
    largest_face = max((f[2] * f[3] for t in tracks for f in t['faces']), default=0)
    result['attributes'].append('close-up' if largest_face > 0.08 else ('medium' if largest_face > 0.015 else 'wide'))
    result.update({'thumbnail': str(thumbnail.relative_to(project)), 'cache_key': key})
    write_json(cache, result)
    return result


def analyze(project: Path, cfg: dict) -> list[dict]:
    film = read_json(project / 'analysis/film.json')
    validate_source(film)
    boundaries, scene_key = detect(project, film, cfg)
    key = signature({'scenes': scene_key, 'sampling': {**cfg['analysis'], 'workers': 1}, 'face_weight': cfg['reframing']['face_weight']})
    shots = []
    # Executor.map only queues cheap shot dictionaries; each worker holds a few small frames.
    cv2.setNumThreads(1)
    with ThreadPoolExecutor(max_workers=min(int(cfg['analysis']['workers']), 4)) as pool:
        for i, result in enumerate(pool.map(lambda s: analyze_one(project, film, s, cfg, key), boundaries), 1):
            result.update(describe(project / result['thumbnail'], project / 'analysis/semantic_cache', cfg['semantic']))
            shots.append(result)
            if i % 50 == 0 or i == len(boundaries):
                LOG.info('[ANALYSIS] %d / %d', i, len(boundaries))
    write_json(project / 'analysis/shots.json', {'schema_version': 1, 'cache_key': key, 'shots': shots})
    LOG.info('[THUMBNAILS] Creating contact sheets')
    sheets = contact_sheets(shots, project)
    write_json(project / 'analysis/contact_sheets.json', sheets)
    LOG.info('[DONE] %d shots indexed. Generate with: python reel.py generate --mood "dreamy nocturnal" --duration 22', len(shots))
    return shots
