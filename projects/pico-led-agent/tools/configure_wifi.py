#!/usr/bin/env python3
"""Prompt privately and upload Wi-Fi configuration without retaining a local copy."""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
import subprocess
import sys
import tempfile


def quoted(value): return repr(value)


def main():
    parser=argparse.ArgumentParser(description="Configure private local-network access on the Pico")
    parser.add_argument("--port",required=True); parser.add_argument("--http-port",type=int,default=80)
    args=parser.parse_args()
    ssid=input("Wi-Fi name: ").strip()
    password=getpass.getpass("Wi-Fi password (hidden): ")
    if not ssid or not password: raise SystemExit("Wi-Fi name and password are required")
    token=secrets.token_urlsafe(24)
    content=("DISPLAY_DRIVER='galactic'\nCOLOR=(40,180,255)\nBRIGHTNESS=.18\nMAX_BRIGHTNESS=.60\nAUTO_BRIGHTNESS=True\nBUTTONS=True\n"
             "SOUND_CUES=False\nFPS=15\nWIFI_ENABLED=True\nWIFI_SSID=%s\nWIFI_PASSWORD=%s\n"
             "HTTP_PORT=%d\nAPI_TOKEN=%s\n"%(quoted(ssid),quoted(password),args.http_port,quoted(token)))
    path=None
    try:
        with tempfile.NamedTemporaryFile("w",delete=False,prefix="pico-led-",suffix=".py") as handle:
            path=handle.name; handle.write(content)
        os.chmod(path,0o600)
        subprocess.run([sys.executable,"-m","mpremote","connect",args.port,"fs","cp",path,":config.py"],check=True)
        subprocess.run([sys.executable,"-m","mpremote","connect",args.port,"reset"],check=True)
    finally:
        if path and os.path.exists(path): os.unlink(path)
    print("Wi-Fi configured. Store this API token in your password manager; it is shown once:")
    print(token)


if __name__=="__main__": main()
