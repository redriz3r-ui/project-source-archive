#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from src.engine import EngineError, ReelEngine


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or resume a film transcript index.")
    parser.add_argument("project_id", help="Existing indexed project id")
    args = parser.parse_args()
    engine = ReelEngine(ROOT)
    try:
        job = engine.start_transcription(args.project_id)
    except EngineError as exc:
        print(f"Could not start transcription: {exc}", file=sys.stderr)
        return 1
    print("Transcription started. Press Control+C to request a safe pause.")
    last_message = None
    try:
        while True:
            status = engine.transcription_status(args.project_id)
            message = f"{status['percent']:5.1f}% · {status['message']}"
            if message != last_message:
                print(message, flush=True)
                last_message = message
            if status["state"] in {"complete", "failed", "paused"}:
                return 0 if status["state"] == "complete" else 1
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nPause requested. The current ten-minute chunk will finish, then progress will be saved.")
        engine.cancel_transcription(args.project_id)
        while True:
            status = engine.transcription_status(args.project_id)
            if status["state"] in {"paused", "complete", "failed"}:
                print(status["message"])
                return 0 if status["state"] in {"paused", "complete"} else 1
            time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())

