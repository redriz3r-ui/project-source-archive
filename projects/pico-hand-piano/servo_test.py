from machine import Pin, PWM
from time import sleep_ms

# Short manual test. Do not save as main.py.
servo = PWM(Pin(15), freq=50, duty_u16=0)
try:
    print('Servo test: centre, short sweep, then stop')
    servo.duty_ns(1500000)
    sleep_ms(500)
    pulses = (list(range(1500, 1701, 10))
              + list(range(1700, 1299, -10))
              + list(range(1300, 1501, 10)))
    for pulse_us in pulses:
        servo.duty_ns(pulse_us * 1000)
        sleep_ms(30)
finally:
    servo.duty_u16(0)
    servo.deinit()
    Pin(15, Pin.OUT, value=0)
    print('PWM off; test finished')
