"""Pico entry point: non-blocking JSON command server plus animation player."""

import json
import sys
import time

try:
    import config
except ImportError:
    class config:
        DISPLAY_DRIVER = "virtual"

from animations import Player
from displays import create

display = create(config)
player = Player(display)


def reply(**fields):
    print(json.dumps(fields))


def handle(message):
    if message.get("v") != 1:
        raise ValueError("unsupported protocol version")
    command = message.get("cmd")
    if command == "ping":
        reply(ok=True, message="pico ready", animation=player.name)
    elif command == "play":
        name = message.get("animation")
        if name not in ("eyes", "rain", "heart", "twinkle"):
            raise ValueError("unknown animation")
        player.play(name, message.get("params", {}).get("speed"))
        reply(ok=True, message="playing " + name)
    elif command == "scroll":
        text = str(message.get("text", ""))[:80]
        if not text:
            raise ValueError("scroll text is empty")
        player.scroll(text, message.get("params", {}).get("speed"))
        reply(ok=True, message="scrolling " + text)
    elif command == "setting":
        name = message.get("name")
        value = message.get("value")
        if name == "brightness":
            display.brightness(max(0, min(15, int(value))))
        elif name == "speed":
            player.speed = max(0.25, min(4.0, float(value)))
        else:
            raise ValueError("unknown setting")
        reply(ok=True, message="updated " + name)
    elif command in ("stop", "clear"):
        player.stop(clear=(command == "clear"))
        reply(ok=True, message=command + "ped" if command == "stop" else "cleared")
    else:
        raise ValueError("unknown command")


try:
    import select
    poller = select.poll()
    poller.register(sys.stdin, select.POLLIN)
except (ImportError, AttributeError):
    poller = None

while True:
    player.tick()
    if poller and poller.poll(0):
        line = sys.stdin.readline()
        if line:
            try:
                handle(json.loads(line))
            except Exception as exc:
                reply(ok=False, error=str(exc))
    time.sleep_ms(10)

