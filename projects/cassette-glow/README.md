# Cassette Glow

A self-running 53 × 11 light animation: two warm, broken reel arcs rotate around
(15, 5) and (37, 5), connected by a slow breathing ribbon. Black/plum space surrounds
burgundy, rose and amber light, with small cream glints. No microphone, network,
external Python packages or music file is required.

## Load with Thonny

1. Use MicroPython firmware compatible with your exact board that provides both
   `galactic` and `picographics`. For a Pico 2 W / RP2350, verify that the firmware
   explicitly supports that processor and the Galactic driver. Standard MicroPython
   does not include these drivers. The published Galactic documentation describes
   RP2040/Pico W; this project does not establish RP2350 firmware compatibility.
2. Connect the board and select the appropriate MicroPython interpreter/port in
   Thonny. In its Shell, check:
   ```python
   from galactic import GalacticUnicorn
   from picographics import PicoGraphics, DISPLAY_GALACTIC_UNICORN
   ```
3. Use Thonny's Files pane to upload `main.py` and the entire `cassette` folder to
   the device root. Keep the folder name and its `__init__.py`. Do not upload the
   enclosing `cassette_glow` folder as an extra nesting level.
4. Open the device's `main.py` and press Run. It also starts at power-up. Stop in
   Thonny to edit; the display clears when the loop exits normally or is interrupted.
   Back up any existing device `main.py` before replacing it.

```text
Device root/
  main.py                  Display setup and timed animation loop
  cassette/
    __init__.py
    settings.py            Palette, brightness and timing
    inputs.py              Demo signals and future normalized input adapter
    render.py              Fractional light placement and trails
    scene.py               Reel and ribbon choreography
```

`tests/` is for desktop verification only.

## Tune the mood

Edit `cassette/settings.py`:

- `BRIGHTNESS = 0.28`: overall hardware brightness, range 0–1.
- `ROTATION_SPEED = 0.48`: reel speed in radians per second.
- `TRAIL_SECONDS = 0.42`: time for old light to decay to about 37%.
- `ATTACK_SECONDS = 0.20`, `RELEASE_SECONDS = 0.85`: input smoothing.
- `FPS = 40`: requested render rate; actual speed depends on firmware/hardware.
- `BACKGROUND = (2, 0, 3)`: set to `(0, 0, 0)` for a fully black background.

Colors are RGB values from 0 to 255. Low spatial coverage and tapered arcs keep
highlights sparse. Physical LEDs may need brightness adjustment for your room.
No controls or sound playback are bound to the board buttons in this initial version.

## How smoothing works

Floating positions distribute light bilinearly to four neighboring LEDs rather
than rounding to one pixel. Continuous time-based phases and exponential attack/
release interpolation smooth changes between frames. A reusable floating-point
history buffer holds the brighter of new light and exponentially decayed old
light, leaving trails without brightness building up indefinitely. A dim halo
softens each source. This uses intensity blending rather than alternating LEDs
with temporal dithering. The driver handles its own gamma correction.

The wave is anchored at both hubs. Its amplitude and spatial stretch change slowly;
it is a designed ribbon, not an audio oscilloscope or a column equalizer.

## Add audio later

The animation consumes an object with `bass`, `mid`, `treble`, and `level`, each
normalized to 0–1. `DemoInput.sample(seconds)` supplies these now. To connect a
future audio analyzer, replace the source in `main.py` with `ExternalInput`:

```python
from cassette.inputs import ExternalInput
source = ExternalInput()
# Inside the loop, before source.sample(elapsed):
source.push(bass=0.4, mid=0.3, treble=0.1, level=0.35)
```

Replace these example values with analyzer readings. Bass controls expansion;
mid controls ribbon amplitude; treble adds a small glint; overall level influences
gain and rotation. Keep capture/analysis outside the renderer. Audio acquisition,
FFT processing and normalization are intentionally future work. Silence preserves
a quiet idle animation. The input adapter holds its last values until pushed again.

## Verification and limits

From this folder, run `python3 tests/check_animation.py` on a desktop. It checks
fractional pixel energy, time-based trail decay, input smoothing/clamping and a
minute of animation for finite values and sparse brightness. Hardware imports
and physical refresh performance need verification on the actual board. The
40 FPS setting is a target, not a measured RP2350 result. If rendering is slower,
the loop skips sleeping and motion remains time-based; pauses over 100 ms are
capped to avoid large visual jumps while debugging.

Official API references:
- [Galactic Unicorn driver](https://github.com/pimoroni/pimoroni-pico/blob/main/micropython/modules/galactic_unicorn/README.md)
- [PicoGraphics](https://github.com/pimoroni/pimoroni-pico/blob/main/micropython/modules/picographics/README.md)
- [Pimoroni Unicorn firmware repository](https://github.com/pimoroni/unicorn)
