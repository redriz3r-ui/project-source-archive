from __future__ import annotations
import cv2
import numpy as np


def gray_small(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2GRAY)


def motion(previous: np.ndarray | None, current: np.ndarray, dt: float) -> dict:
    if previous is None:
        return {'motion_score': 0.0, 'camera_flow': [0.0, 0.0], 'residual_motion': 0.0,
                'subject': [0.5, 0.5], 'visual_change': 0.0}
    flow = cv2.calcOpticalFlowFarneback(previous, current, None, 0.5, 2, 15, 2, 5, 1.2, 0)
    median = np.median(flow.reshape(-1, 2), axis=0)
    residual = np.linalg.norm(flow - median, axis=2)
    weights = np.maximum(residual - np.percentile(residual, 80), 0)
    total = weights.sum()
    if total > 1:
        yy, xx = np.indices(weights.shape)
        subject = [float((xx * weights).sum() / total / 160), float((yy * weights).sum() / total / 90)]
    else:
        subject = [0.5, 0.5]
    speed = np.linalg.norm(flow, axis=2).mean() / max(dt, 0.05) / 30
    return {'motion_score': float(min(1, speed)), 'camera_flow': [float(v / max(dt, 0.05)) for v in median],
            'residual_motion': float(min(1, residual.mean() / max(dt, 0.05) / 20)), 'subject': subject,
            'visual_change': float(cv2.absdiff(previous, current).mean() / 255)}
