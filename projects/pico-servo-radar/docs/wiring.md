# Wiring

Disconnect the Pico's USB cable before changing any wiring.

## Stage 1: servo-only test

| SG90 lead | Pico connection | Physical pin |
| --- | --- | ---: |
| Brown (ground) | GND | 38 |
| Red (power) | VBUS | 40 |
| Orange/yellow (signal) | GP15 | 20 |

The servo horn will move as soon as the test starts. Keep fingers, wires, and
the unmounted ultrasonic sensor away from it. This USB-powered arrangement is
only for an unloaded first test. Stop if the Pico resets repeatedly, the servo
chatters continuously, a component gets hot, or there is a burning smell.

Do not connect the ultrasonic sensor during this stage.

