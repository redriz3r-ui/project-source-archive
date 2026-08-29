from streamclip.config import Config
from streamclip.detection import build_windows, detect_candidates
from streamclip.models import ChatMessage


def messages_with_bursts():
    messages = []
    # Stable high-volume baseline: 20 messages every 5 seconds for ten minutes.
    for window in range(120):
        count = 120 if window in (60, 61) else 20
        for i in range(count):
            text = "LMAO NO WAY CLIP" if window in (60, 61) else f"normal {i}"
            messages.append(ChatMessage(window * 5 + i / max(count, 1), f"user-{i}", text))
    return messages


def test_detects_normalized_burst_in_high_volume_chat():
    config = Config(z_threshold=3, merge_gap_seconds=10)
    windows = build_windows(messages_with_bursts(), config)
    candidates = detect_candidates(windows, config)
    assert candidates
    assert 295 <= candidates[0].peak_timestamp <= 305
    assert candidates[0].peak_messages == 120
    assert candidates[0].reaction_density == 1.0


def test_neighboring_spikes_are_merged():
    config = Config(z_threshold=3, merge_gap_seconds=10)
    candidates = detect_candidates(build_windows(messages_with_bursts(), config), config)
    matching = [c for c in candidates if 295 <= c.peak_timestamp <= 305]
    assert len(matching) == 1
    assert matching[0].event_end - matching[0].event_start >= 10


def test_empty_chat_is_safe():
    config = Config()
    assert build_windows([], config) == []
    assert detect_candidates([], config) == []

