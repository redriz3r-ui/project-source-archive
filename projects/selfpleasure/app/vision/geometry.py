"""Pure facial geometry independent of MediaPipe and camera hardware."""

from dataclasses import dataclass
from math import hypot
from typing import Protocol, Sequence


class Point(Protocol):
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class MouthGeometry:
    x: float
    y: float
    openness: float
    width: float
    region: tuple[float, float, float, float]


def mouth_geometry(landmarks: Sequence[Point]) -> MouthGeometry | None:
    """Return normalized mouth center and lip gap relative to mouth width.

    MediaPipe indices: 13/14 are inner upper/lower lip; 61/291 are corners.
    The ratio is approximately scale invariant as a face moves toward camera.
    """
    if len(landmarks) <= 291:
        return None
    upper, lower = landmarks[13], landmarks[14]
    left, right = landmarks[61], landmarks[291]
    width = hypot(right.x - left.x, right.y - left.y)
    if width < 1e-6:
        return None
    gap = hypot(lower.x - upper.x, lower.y - upper.y)
    lip_indices = (0, 13, 14, 17, 40, 61, 84, 91, 267, 270, 291, 314, 321)
    xs = [landmarks[index].x for index in lip_indices if index < len(landmarks)]
    ys = [landmarks[index].y for index in lip_indices if index < len(landmarks)]
    left_edge, right_edge = max(0.0, min(xs)), min(1.0, max(xs))
    top_edge, bottom_edge = max(0.0, min(ys)), min(1.0, max(ys))
    return MouthGeometry(
        x=max(0.0, min(1.0, (upper.x + lower.x + left.x + right.x) / 4)),
        y=max(0.0, min(1.0, (upper.y + lower.y + left.y + right.y) / 4)),
        openness=max(0.0, min(1.0, gap / width)),
        width=width,
        region=(left_edge, top_edge, right_edge - left_edge, bottom_edge - top_edge),
    )
