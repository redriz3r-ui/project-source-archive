#!/usr/bin/env python3
"""Reversible Pico v2 deployment using the official mpremote utility."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[1]
FILES = ("main.py", "runtime.py", "effects.py", "display.py", "controls.py", "wifi_server.py")


def command(port, *args):
    return [sys.executable, "-m", "mpremote", "connect", port, *args]


def run(args, dry_run=False):
    print(" ".join(args))
    if not dry_run:
        subprocess.run(args, check=True, cwd=ROOT)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install(port, dry_run):
    # Copy remote startup locally first; the local backup is timestamp-independent and inspectable.
    backup = ROOT / "work" / "device_backup" / "main.py"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        run(command(port, "fs", "cp", ":main.py", str(backup)), dry_run)
    else:
        print("Preserving existing local backup:", backup)
    for name in FILES:
        run(command(port, "fs", "cp", str(ROOT / "pico_v2" / name), ":" + name), dry_run)
    config = ROOT / "pico_v2" / "config.py"
    if config.exists(): run(command(port, "fs", "cp", str(config), ":config.py"), dry_run)
    if dry_run:
        print("Would download and verify every uploaded file before reset")
    else:
        with tempfile.TemporaryDirectory(prefix="pico-led-verify-") as directory:
            for name in FILES:
                downloaded=Path(directory)/name
                run(command(port,"fs","cp",":"+name,str(downloaded)))
                if sha256(downloaded)!=sha256(ROOT/"pico_v2"/name):
                    raise RuntimeError("device verification failed for "+name)
        print("Verified every uploaded file byte-for-byte")
    run(command(port, "reset"), dry_run)
    print("Local source hashes:")
    for name in FILES: print(name, sha256(ROOT / "pico_v2" / name))


def restore(port, dry_run):
    backup = ROOT / "work" / "device_backup" / "main.py"
    if not backup.exists() and not dry_run: raise SystemExit("No local startup backup found")
    run(command(port, "fs", "cp", str(backup), ":main.py"), dry_run)
    run(command(port, "reset"), dry_run)


def main():
    parser=argparse.ArgumentParser(description="Safely install or restore Pico LED Agent v2")
    parser.add_argument("action",choices=("install","restore")); parser.add_argument("--port",required=True)
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args()
    (install if args.action=="install" else restore)(args.port,args.dry_run)


if __name__=="__main__": main()
