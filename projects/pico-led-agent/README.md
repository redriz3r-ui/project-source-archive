# Pico W LED Agent

Version 2 is now the primary Galactic Unicorn implementation. See [V2.md](V2.md)
for rich scenes, the full 53×11 RGB renderer, Wi-Fi, physical controls, audio
architecture, frame streaming, deployment and recovery.

A small local agent that turns natural-language commands into animations on an
8×8 LED matrix attached to a Raspberry Pi Pico W.

The first version is deliberately simple:

```text
your words → deterministic Mac parser → one-line JSON → USB serial → Pico W
```

It includes a terminal simulator, so the Mac-side agent can be tested before
the LED matrix is wired.

## 1. Try it without hardware

Requires Python 3.10 or newer and has no dependencies in simulator mode.

```bash
python3 -m led_agent --transport sim "show blinking eyes"
python3 -m led_agent --transport sim "make rain"
python3 -m led_agent --transport sim "scroll HELLO"
python3 -m led_agent --transport sim
```

The final command starts an interactive prompt. Other supported commands
include `heart`, `twinkle`, `clear`, `stop`, `brightness 4`, and `speed 2`.

## 2. Install the Mac agent for USB use

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[serial]'
```

Copy everything inside `pico/` to the root of the Pico W using Thonny. Rename
`pico/config.example.py` to `config.py`, then select the correct display driver
there. The detected target is a Pimoroni Galactic Unicorn, whose native driver
is included. `MAX7219` is also available for a separate 8x8 module.

After restarting the Pico, find it and send a command:

```bash
python -m led_agent --list-ports
python -m led_agent --port /dev/cu.usbmodemXXXX "show blinking eyes"
```

On macOS, prefer `/dev/cu.*` over `/dev/tty.*`. If auto-detection finds exactly
one likely USB serial device, `--port` can be omitted.

## Architecture

- `led_agent/parser.py`: converts friendly text into a stable command object.
- `led_agent/transports.py`: sends newline-delimited JSON over USB, or renders
  locally in the simulator.
- `pico/main.py`: validates commands and owns animation playback.
- `pico/displays.py`: hardware boundary. Add another matrix by implementing
  `pixel(x, y, value)`, `fill(value)`, and `show()`.
- `protocol.md`: the versioned contract between the Mac and Pico.

The Pico owns animation timing. The Mac sends a small instruction once, then
can disconnect without freezing the display.

## Hardware note

Do not wire the matrix based only on this repository. Confirm its exact model,
voltage, and pin labels first. A MAX7219 module, a WS2812/NeoPixel matrix, and a
bare row/column matrix need different wiring and drivers. The default config is
`virtual`, so uploading the code before choosing a driver is harmless.

## Test

```bash
python3 -m unittest discover -s tests -v
```
