"""Metrics over manually labeled numeric observations; no camera/device imports."""

from statistics import mean


POSITIVE = "INTENDED"
NEGATIVE = "NO_INTERACTION"
UNCERTAIN = "UNCERTAIN"
LABELS = frozenset((POSITIVE, NEGATIVE, UNCERTAIN))


def score_samples(samples: list[dict[str, object]]) -> dict[str, object]:
    """Score INTERACTION_ACTIVE against subjective interval labels.

    Uncertain frames are excluded. Rates are descriptive, not calibrated
    probabilities or evidence of physical contact. Gap time is not counted as
    observed negative time.
    """
    tp = fp = tn = fn = false_episodes = missed = unresolved_ends = intended_intervals = 0
    start_latencies: list[float] = []
    end_latencies: list[float] = []
    negative_seconds = 0.0
    for index, sample in enumerate(samples):
        label = sample["label"]
        predicted = sample["state"] == "INTERACTION_ACTIVE"
        if label == POSITIVE:
            tp += predicted
            fn += not predicted
        elif label == NEGATIVE:
            fp += predicted
            tn += not predicted
            if predicted and (index == 0 or samples[index - 1]["label"] != NEGATIVE or
                              samples[index - 1]["state"] != "INTERACTION_ACTIVE"):
                false_episodes += 1
            if index + 1 < len(samples) and samples[index + 1]["label"] == NEGATIVE:
                negative_seconds += min(0.25, max(0.0,
                    float(samples[index + 1]["elapsed_s"]) - float(sample["elapsed_s"])))
    for index, sample in enumerate(samples):
        if sample["label"] != POSITIVE or (index > 0 and samples[index - 1]["label"] == POSITIVE):
            continue
        intended_intervals += 1
        end = next((j for j in range(index, len(samples)) if samples[j]["label"] != POSITIVE), len(samples))
        first_active = next((j for j in range(index, end)
                             if samples[j]["state"] == "INTERACTION_ACTIVE"), None)
        if first_active is None:
            missed += 1
        else:
            start_latencies.append(round(float(samples[first_active]["elapsed_s"]) -
                                         float(sample["elapsed_s"]), 3))
        if first_active is not None and end < len(samples) and samples[end]["label"] == NEGATIVE:
            next_positive = next((j for j in range(end, len(samples))
                                  if samples[j]["label"] != NEGATIVE), len(samples))
            first_off = next((j for j in range(end, next_positive)
                              if samples[j]["state"] != "INTERACTION_ACTIVE"), None)
            if first_off is None:
                unresolved_ends += 1
            else:
                end_latencies.append(round(float(samples[first_off]["elapsed_s"]) -
                                           float(samples[end]["elapsed_s"]), 3))
    labeled = tp + fp + tn + fn
    if negative_seconds < 300 or intended_intervals < 10:
        recommendation = "INSUFFICIENT_DATA: collect more labeled negative time and intended intervals before choosing a model."
    elif false_episodes or missed:
        recommendation = "REVIEW_HEURISTIC: inspect errors and tune calibration; consider a local model only if failures repeat across held-out sessions."
    else:
        recommendation = "RETAIN_PROVISIONALLY: no errors observed in this session; repeat under different conditions before trusting the heuristic."
    return {
        "total_frames": len(samples), "labeled_frames": labeled,
        "uncertain_frames": len(samples) - labeled,
        "true_positive": tp, "false_positive": fp,
        "true_negative": tn, "false_negative": fn,
        "precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "false_positive_episodes": false_episodes,
        "negative_labeled_seconds": round(negative_seconds, 3),
        "false_positive_episodes_per_hour": round(false_episodes * 3600 / negative_seconds, 2)
            if negative_seconds > 0 else None,
        "missed_interactions": missed,
        "intended_intervals": intended_intervals,
        "start_latencies_s": start_latencies,
        "mean_start_latency_s": round(mean(start_latencies), 3) if start_latencies else None,
        "end_latencies_s": end_latencies,
        "mean_end_latency_s": round(mean(end_latencies), 3) if end_latencies else None,
        "unresolved_ends": unresolved_ends,
        "recommendation": recommendation,
    }
