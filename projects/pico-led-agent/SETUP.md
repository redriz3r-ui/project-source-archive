# Guided setup

## Phase A — prove the agent on the Mac

From this folder, run:

```bash
python3 -m led_agent --transport sim "scroll HELLO"
```

If the parsed JSON says `"cmd": "scroll"` and the terminal shows a preview,
the language-to-command half is working.

## Phase B — identify the matrix

The connected board identified itself as a **Pimoroni Galactic Unicorn with a
Pico 2 W**. It has a built-in 53×11 RGB matrix, and its native firmware modules
(`galactic` and `picographics`) are already installed.

For any future separate matrix, read the labels before connecting power:

- A MAX7219 module usually has `DIN`, `CS`, `CLK`, `VCC`, and `GND`.
- A WS2812/NeoPixel matrix usually has `DIN`, `5V`/`VCC`, and `GND`, often
  with arrows showing data direction.
- A bare matrix has many row/column pins and needs extra drive circuitry.

This release includes Galactic Unicorn and MAX7219 drivers.

## Phase C — load MicroPython and firmware

1. Install current MicroPython on the Pico W using Thonny's interpreter setup.
2. In Thonny, copy `pico/main.py`, `pico/animations.py`, and
   `pico/displays.py` to the Pico root.
3. Copy `pico/config.example.py` to the Pico root as `config.py`.
4. For a confirmed MAX7219 module, set `DISPLAY_DRIVER = "max7219"` and review
   every pin in `config.py` against the labels on your board.
5. Restart the Pico. The animation may remain blank until the first command.

Do not leave Thonny connected while using the command agent; only one program
can normally own the serial port at a time.

## Phase D — USB handshake

Install the one optional dependency and list ports:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[serial]'
python -m led_agent --list-ports
```

Then check the protocol before trying an animation:

```bash
python -m led_agent --port /dev/cu.usbmodemXXXX "ping"
python -m led_agent --port /dev/cu.usbmodemXXXX "brightness 1"
python -m led_agent --port /dev/cu.usbmodemXXXX "show blinking eyes"
```

Start at low brightness. If the image is mirrored or rotated, change only
`ROTATION`, `FLIP_X`, or `FLIP_Y` in `config.py` and restart.

## Troubleshooting

- **No port:** use a USB data cable, not a charge-only cable; reconnect while
  holding BOOTSEL only when reinstalling firmware.
- **Permission/busy error:** disconnect Thonny's interpreter, close other serial
  monitors, and retry.
- **Pico does not reply:** confirm all four firmware files are on the device and
  inspect Thonny's console for a startup exception.
- **Reply is unexpected:** press Ctrl-D in Thonny to soft-reboot, disconnect
  Thonny, and retry `ping`.
- **Pixels are scrambled:** stop and confirm the matrix model. Do not solve an
  electrical mismatch with orientation settings.

## Next extension: Wi-Fi

USB is the first transport because it avoids credentials, discovery, sockets,
and network failure modes. The JSON protocol is transport-neutral. A later
Wi-Fi transport can send the exact same lines to a small TCP server on the
Pico, while keeping USB as a recovery path.
