"""Slow, conservative SG90 servo test for a Raspberry Pi Pico.

Wiring used by this test:
    SG90 brown  -> Pico GND (physical pin 38)
    SG90 red    -> Pico VBUS (physical pin 40, 5 V from USB)
    SG90 orange -> Pico GP15 (physical pin 20)

Run with MicroPython. Keep the servo horn clear while powering on.
"""

from machine import Pin, PWM
from time import sleep_ms


SERVO_PIN = 15
PWM_FREQUENCY_HZ = 50
MIN_ANGLE = 30
MAX_ANGLE = 150
STEP_DEGREES = 2
STEP_DELAY_MS = 35

# Conservative SG90 pulse range. Avoids forcing the servo against its stops.
MIN_PULSE_US = 600
MAX_PULSE_US = 2400
PWM_PERIOD_US = 20_000


servo = PWM(Pin(SERVO_PIN))
servo.freq(PWM_FREQUENCY_HZ)


def set_angle(angle):
    """Move the servo to an angle between 0 and 180 degrees."""
    angle = max(0, min(180, angle))
    pulse_us = MIN_PULSE_US + (
        (MAX_PULSE_US - MIN_PULSE_US) * angle // 180
    )
    duty_u16 = pulse_us * 65_535 // PWM_PERIOD_US
    servo.duty_u16(duty_u16)


def sweep():
    """Sweep slowly between conservative endpoints."""
    while True:
        for angle in range(MIN_ANGLE, MAX_ANGLE + 1, STEP_DEGREES):
            set_angle(angle)
            print("ANGLE,{}".format(angle))
            sleep_ms(STEP_DELAY_MS)

        for angle in range(MAX_ANGLE, MIN_ANGLE - 1, -STEP_DEGREES):
            set_angle(angle)
            print("ANGLE,{}".format(angle))
            sleep_ms(STEP_DELAY_MS)


try:
    set_angle(90)
    sleep_ms(1000)
    sweep()
finally:
    servo.deinit()

