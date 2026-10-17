"""Application entry point. The server is intentionally loopback-only."""

import argparse
from dataclasses import replace

import uvicorn

from app.api import create_app
from app.config import settings

app = create_app(settings)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--off-body-manual-bench", action="store_true",
                        help="Temporarily enable manual-only real-device tests, capped at 20% and 0.5 s")
    args = parser.parse_args()
    run_settings = (replace(settings, real_device_manual_bench_enabled=True,
                            max_intensity=0.20, max_duration_seconds=0.5)
                    if args.off_body_manual_bench else settings)
    uvicorn.run(create_app(run_settings), host=run_settings.host,
                port=run_settings.port, reload=False, access_log=False)


if __name__ == "__main__":
    main()
