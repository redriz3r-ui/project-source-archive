from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


def app_token(client_id: str, client_secret: str) -> str:
    body = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }).encode()
    request = urllib.request.Request("https://id.twitch.tv/oauth2/token", data=body, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["access_token"]


def get_clips(client_id: str, token: str, broadcaster_id: str, started_at: str, ended_at: str) -> list[dict]:
    clips: list[dict] = []
    cursor = ""
    while True:
        params = {"broadcaster_id": broadcaster_id, "started_at": started_at,
                  "ended_at": ended_at, "first": 100}
        if cursor:
            params["after"] = cursor
        url = "https://api.twitch.tv/helix/clips?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={
            "Client-Id": client_id,
            "Authorization": f"Bearer {token}",
        })
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
        clips.extend(payload.get("data", []))
        cursor = payload.get("pagination", {}).get("cursor", "")
        if not cursor or len(clips) >= 1000:
            break
    return clips


def compare(clips: list[dict], candidates: list[dict], vod_id: str, tolerance: float = 30) -> list[dict]:
    peaks = [float(candidate["peak_timestamp"]) for candidate in candidates]
    rows = []
    for clip in clips:
        if str(clip.get("video_id")) != str(vod_id) or clip.get("vod_offset") is None:
            continue
        offset = float(clip["vod_offset"])
        nearest = min(peaks, key=lambda peak: abs(peak - offset)) if peaks else None
        distance = abs(nearest - offset) if nearest is not None else None
        rows.append({
            "clip_id": clip.get("id", ""), "title": clip.get("title", ""),
            "vod_offset": offset, "view_count": int(clip.get("view_count", 0)),
            "duration": clip.get("duration", 0), "nearest_peak": nearest,
            "distance_seconds": distance, "detected_within_tolerance": distance is not None and distance <= tolerance,
            "url": clip.get("url", ""),
        })
    return sorted(rows, key=lambda row: row["view_count"], reverse=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare detected moments with public Twitch clips")
    parser.add_argument("--candidates", default="runs/adapt-alaska/candidates.json")
    parser.add_argument("--vod-id", required=True)
    parser.add_argument("--broadcaster-id", required=True)
    parser.add_argument("--started-at", required=True, help="RFC3339 stream start")
    parser.add_argument("--duration", type=int, required=True, help="VOD duration in seconds")
    parser.add_argument("--output", default="runs/twitch-clip-comparison")
    parser.add_argument("--tolerance", type=float, default=30)
    args = parser.parse_args(argv)
    client_id = os.environ.get("TWITCH_CLIENT_ID")
    client_secret = os.environ.get("TWITCH_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("error: set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET from a registered Twitch app", file=sys.stderr)
        return 2
    start = datetime.fromisoformat(args.started_at.replace("Z", "+00:00")).astimezone(timezone.utc)
    end = start + timedelta(seconds=args.duration)
    token = app_token(client_id, client_secret)
    clips = get_clips(client_id, token, args.broadcaster_id,
                      start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z"))
    candidates = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    rows = compare(clips, candidates, args.vod_id, args.tolerance)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    with (output / "comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["clip_id", "vod_offset"])
        writer.writeheader()
        writer.writerows(rows)
    hits = sum(row["detected_within_tolerance"] for row in rows)
    print(f"Matched {hits}/{len(rows)} VOD clips within {args.tolerance:g}s. Results: {output}")
    return 0

