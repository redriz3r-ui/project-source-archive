"""Streaming cut detection with histogram/pixel evidence and flash rejection."""
from __future__ import annotations
from pathlib import Path
import cv2
import numpy as np
from .utils import LOG, read_json, signature, write_json


def descriptor(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    small = cv2.resize(frame, (96, 54))
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    histogram = cv2.calcHist([hsv], [0, 1], None, [24, 16], [0, 180, 0, 256])
    cv2.normalize(histogram, histogram)
    return small, histogram


def difference(a: tuple, b: tuple) -> float:
    pixels = float(np.mean(cv2.absdiff(a[0], b[0]))) / 255
    histogram = cv2.compareHist(a[1], b[1], cv2.HISTCMP_BHATTACHARYYA)
    return 0.65 * histogram + 0.35 * pixels


def detect(project: Path, film: dict, cfg: dict) -> tuple[list[dict], str]:
    settings = cfg['analysis']
    key = signature({'proxy': film['proxy_key'], 'threshold': settings['cut_threshold'],
                     'min': settings['minimum_shot_seconds'],
                     'continuous_segment_seconds': settings.get('continuous_segment_seconds', 12),
                     'version': settings['algorithm_version'], 'detector_version': 4})
    path = project / 'analysis/scenes.json'
    if path.exists():
        saved = read_json(path)
        if saved['cache_key'] == key:
            LOG.info('[SCENES] Reusing %d shots', len(saved['shots']))
            return saved['shots'], key
    LOG.info('[SCENES] Detecting cuts (streaming proxy)')
    cap = cv2.VideoCapture(film['proxy'])
    if not cap.isOpened():
        raise RuntimeError('OpenCV could not open analysis proxy')
    fps = cap.get(cv2.CAP_PROP_FPS)
    expected_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0:
        cap.release()
        raise RuntimeError('Proxy has no usable frame rate')
    cuts = [0.0]
    previous = pending = None
    index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            current = descriptor(frame)
            stamp = index / fps
            flash_return = False
            if pending is not None:
                when, before = pending
                # A frame returning to its pre-cut appearance is a flash, not two cuts.
                if difference(before, current) >= settings['cut_threshold'] * 0.7:
                    cuts.append(when)
                else:
                    flash_return = True
                pending = None
            if not flash_return and previous is not None and stamp - cuts[-1] >= settings['minimum_shot_seconds']:
                if difference(previous, current) >= settings['cut_threshold']:
                    pending = (stamp, previous)
            previous = current
            index += 1
    finally:
        cap.release()
    if index < 2 or (expected_frames > 0 and index < expected_frames - 2):
        raise RuntimeError(f'Incomplete proxy decode: {index} of {expected_frames} frames')
    duration = min(film['duration'], index / fps)
    cuts = sorted(set(t for t in cuts if t < duration - settings['minimum_shot_seconds'])) or [0.0]
    # A continuous take still needs distinct intervals for ranking and editing.
    # Keep detected cuts intact; divide only an otherwise uncut video.
    segment_seconds = float(settings.get('continuous_segment_seconds', 12))
    if len(cuts) == 1 and duration > segment_seconds:
        cuts.extend(i * segment_seconds for i in range(1, int(duration // segment_seconds))
                    if duration - i * segment_seconds >= settings['minimum_shot_seconds'])
    cuts.append(duration)
    shots = [{'shot_id': i + 1, 'scene_id': i + 1, 'start': round(a, 6), 'end': round(b, 6),
              'duration': round(b - a, 6)} for i, (a, b) in enumerate(zip(cuts, cuts[1:]))]
    write_json(path, {'cache_key': key, 'method': 'histogram-pixel-cut-v1', 'shots': shots})
    LOG.info('[SCENES] %d shots detected', len(shots))
    return shots, key
