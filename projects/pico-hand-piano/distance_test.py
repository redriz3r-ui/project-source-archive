from machine import Pin, time_pulse_us
from time import sleep_us, sleep_ms

# Stationary, finite test. No servo PWM; no automatic startup.
Pin(15, Pin.OUT, value=0)
trig = Pin(13, Pin.OUT, value=0)
echo = Pin(14, Pin.IN)
sleep_ms(100)
try:
    for sample in range(1, 11):
        trig.value(0)
        sleep_us(2)
        trig.value(1)
        sleep_us(10)
        trig.value(0)
        pulse = time_pulse_us(echo, 1, 30000)
        if pulse < 0:
            print('Reading', sample, ': no echo (timeout', pulse, ')')
        else:
            print('Reading', sample, ':', round(pulse * 0.0343 / 2, 1), 'cm')
        sleep_ms(250)
finally:
    trig.value(0)
    Pin(15, Pin.OUT, value=0)
    print('Distance test finished; servo signal off')
