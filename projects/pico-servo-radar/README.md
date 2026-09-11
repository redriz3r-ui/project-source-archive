# Pico Servo Radar

A starter project for a scanning ultrasonic “radar” built with a Raspberry Pi Pico WH, an SG90 servo, and an HC-SR04-style distance sensor.

## Project layout

- `firmware/` — MicroPython code that runs on the Pico
- `mac/` — visualization software that runs on the Mac
- `docs/` — wiring notes, build instructions, and design documentation
- `assets/` — images, diagrams, screenshots, and other media
- `experiments/` — small hardware and software tests

## Getting started

1. Follow `docs/wiring.md` to connect the servo-only test circuit.
2. Run `experiments/servo_test.py` on the Pico with MicroPython.
3. Test the ultrasonic sensor separately before combining the hardware.
4. Copy the completed `firmware/main.py` to the Pico as `main.py`.
5. Create a Python virtual environment on the Mac and install `requirements.txt`.
6. Run `mac/radar_visualizer.py`, selecting the Pico's serial port when prompted.

The starter code is intentionally minimal. Confirm voltage requirements and wiring before powering the ultrasonic sensor.
