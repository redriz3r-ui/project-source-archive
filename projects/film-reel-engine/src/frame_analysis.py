from __future__ import annotations
import cv2
import numpy as np


def measure(frame: np.ndarray) -> dict:
    image = cv2.resize(frame, (160, 90))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hist = np.bincount(gray.ravel(), minlength=256).astype(float)
    probabilities = hist[hist > 0] / gray.size
    entropy = float(-np.sum(probabilities * np.log2(probabilities)) / 8)
    rgb = image[:, :, ::-1].astype(float)
    rg, yb = rgb[:, :, 0] - rgb[:, :, 1], (rgb[:, :, 0] + rgb[:, :, 1]) / 2 - rgb[:, :, 2]
    colorful = (np.hypot(rg.std(), yb.std()) + 0.3 * np.hypot(rg.mean(), yb.mean())) / 150
    # Small quantized histogram is deterministic and cheaper than repeated k-means.
    bins = (rgb // 32).astype(int)
    codes = bins[:, :, 0] * 64 + bins[:, :, 1] * 8 + bins[:, :, 2]
    common = np.argsort(np.bincount(codes.ravel(), minlength=512))[-3:][::-1]
    colors = [[int(c // 64 * 32 + 16), int(c // 8 % 8 * 32 + 16), int(c % 8 * 32 + 16)] for c in common]
    return {'brightness': float(gray.mean() / 255), 'contrast': float(gray.std() / 128),
            'saturation': float(hsv[:, :, 1].mean() / 255), 'entropy': entropy,
            'edge_density': float((cv2.Canny(gray, 70, 150) > 0).mean()),
            'darkness': float((gray < 45).mean()), 'colorfulness': float(min(1, colorful)),
            'dominant_colors': colors, 'mean_color': (rgb.mean(axis=(0, 1)) / 255).tolist()}
