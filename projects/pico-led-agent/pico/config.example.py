# This project was detected on a Pimoroni Galactic Unicorn (53x11 RGB).
DISPLAY_DRIVER = "galactic"  # "galactic", "virtual", or "max7219"

# Foreground colour for the Galactic Unicorn animations.
COLOR = (40, 180, 255)

# MAX7219 8x8 module, Pico W physical wiring:
# VCC -> VBUS (5V), GND -> GND, DIN -> GP3, CS -> GP5, CLK -> GP2
# Logic-level requirements vary by module; confirm your module before wiring.
SPI_ID = 0
PIN_SCK = 2
PIN_MOSI = 3
PIN_CS = 5

# Orientation corrections, applied in software.
ROTATION = 0  # 0, 90, 180, or 270
FLIP_X = False
FLIP_Y = False
BRIGHTNESS = 3  # Agent range: 0..15 (mapped to 0.0..1.0 on Galactic)
