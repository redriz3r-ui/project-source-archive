from streamclip.twitch_compare import compare


def test_matches_clip_offsets_to_nearest_detected_peak():
    clips = [{"id": "clip", "video_id": "123", "vod_offset": 105,
              "view_count": 500, "duration": 30, "title": "moment", "url": "https://example.test"}]
    candidates = [{"peak_timestamp": 100}, {"peak_timestamp": 400}]
    rows = compare(clips, candidates, "123", tolerance=10)
    assert rows[0]["nearest_peak"] == 100
    assert rows[0]["distance_seconds"] == 5
    assert rows[0]["detected_within_tolerance"] is True


def test_excludes_clips_from_other_vods():
    clips = [{"id": "wrong", "video_id": "999", "vod_offset": 100, "view_count": 1}]
    assert compare(clips, [{"peak_timestamp": 100}], "123") == []
