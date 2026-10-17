"""Offline, numeric-only evaluation of interaction states; never opens a camera/device."""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from app.vision.calibration import Calibration
from app.vision.interaction import InteractionEstimator, InteractionState
from app.vision.object_tracker import ObjectObservation
from app.vision.service import FaceObservation


DEFAULT_CASES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "recognition_cases.json"


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    frames: int
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    precision: float | None
    recall: float | None
    false_positive_rate: float | None
    false_activation_episodes: int
    start_latencies_s: tuple[float, ...]
    end_latencies_s: tuple[float, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "frames": self.frames,
            "true_positive": self.true_positive,
            "false_positive": self.false_positive,
            "true_negative": self.true_negative,
            "false_negative": self.false_negative,
            "precision": self.precision,
            "recall": self.recall,
            "false_positive_rate": self.false_positive_rate,
            "false_activation_episodes": self.false_activation_episodes,
            "start_latencies_s": list(self.start_latencies_s),
            "end_latencies_s": list(self.end_latencies_s),
        }


def evaluate_cases(path: Path = DEFAULT_CASES) -> BenchmarkResult:
    """Replay hand-labeled trajectories; labels are intent, not detected contact.

    No frames are captured or written. Test cases are deliberately non-explicit
    synthetic prop motions and cannot establish real-world recognition accuracy.
    """
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("Expected a non-empty list of benchmark cases")
    tp = fp = tn = fn = episodes = 0
    starts: list[float] = []
    ends: list[float] = []
    for case in cases:
        estimator = InteractionEstimator()
        config = Calibration(**case.get("calibration", {}))
        interval = float(case.get("interval_s", 0.1))
        if interval <= 0 or not case.get("samples"):
            raise ValueError("Each case needs samples and a positive frame interval")
        truth = []
        predicted = []
        for index, sample in enumerate(case["samples"]):
            if not isinstance(sample.get("active"), bool):
                raise ValueError(f"{case['name']} sample {index} needs a manual active label")
            face_present = sample.get("face", True)
            object_present = sample.get("object", True)
            face = FaceObservation(
                face_detected=face_present, mouth_detected=face_present,
                mouth_x=sample.get("mouth_x", 0.5) if face_present else None,
                mouth_y=sample.get("mouth_y", 0.5) if face_present else None,
                mouth_width=sample.get("mouth_width", 0.12) if face_present else None,
                mouth_openness=sample.get("openness", 0.2) if face_present else None,
                tracking_quality=sample.get("face_quality", 0.95) if face_present else 0.0,
                frame_aspect_ratio=sample.get("aspect_ratio", 4 / 3),
            )
            obj = ObjectObservation(
                detected=object_present,
                x=sample.get("x") if object_present else None,
                y=sample.get("y", 0.5) if object_present else None,
                tracking_quality=sample.get("object_quality", 0.9) if object_present else 0.0,
            )
            if object_present and obj.x is None:
                raise ValueError(f"{case['name']} sample {index} needs x")
            state = estimator.update(face, obj, index * interval, config).state
            actual = sample["active"]
            output = state == InteractionState.INTERACTION_ACTIVE
            truth.append(actual)
            predicted.append(output)
            tp += actual and output
            fp += not actual and output
            tn += not actual and not output
            fn += actual and not output
            if output and not actual and (index == 0 or not (predicted[index - 1] and truth[index - 1] is False)):
                episodes += 1
        for index in range(1, len(truth)):
            if truth[index] and not truth[index - 1]:
                event_end = next((j for j in range(index, len(truth)) if not truth[j]), len(truth))
                match = next((j for j in range(index, event_end) if predicted[j]), None)
                if match is not None:
                    starts.append(round((match - index) * interval, 3))
            if not truth[index] and truth[index - 1]:
                next_event = next((j for j in range(index, len(truth)) if truth[j]), len(truth))
                match = next((j for j in range(index, next_event) if not predicted[j]), None)
                if match is not None:
                    ends.append(round((match - index) * interval, 3))
    return BenchmarkResult(
        frames=tp + fp + tn + fn,
        true_positive=tp, false_positive=fp, true_negative=tn, false_negative=fn,
        precision=round(tp / (tp + fp), 3) if tp + fp else None,
        recall=round(tp / (tp + fn), 3) if tp + fn else None,
        false_positive_rate=round(fp / (fp + tn), 3) if fp + tn else None,
        false_activation_episodes=episodes,
        start_latencies_s=tuple(starts), end_latencies_s=tuple(ends),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", nargs="?", type=Path, default=DEFAULT_CASES)
    args = parser.parse_args()
    print(json.dumps(evaluate_cases(args.cases).as_dict(), indent=2))


if __name__ == "__main__":
    main()
