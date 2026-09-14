from machine import Pin, PWM, time_pulse_us
from time import sleep_ms, sleep_us

trig = Pin(13, Pin.OUT, value=0)
echo = Pin(14, Pin.IN)
servo = PWM(Pin(15), freq=50, duty_u16=0)
try:
    print('Small scan starting')
    for pulse_us in (1500, 1400, 1300, 1400, 1500, 1600, 1700, 1600, 1500):
        servo.duty_ns(pulse_us * 1000)
        sleep_ms(350)
        trig.value(0)
        sleep_us(2)
        trig.value(1)
        sleep_us(10)
        trig.value(0)
        pulse = time_pulse_us(echo, 1, 30000)
        if pulse < 0:
            print('Position', pulse_us, 'us: no echo')
        else:
            cm = pulse * 0.0343 / 2
            print('Position', pulse_us, 'us:', round(cm, 1), 'cm /', round(cm / 2.54, 1), 'inches')
finally:
    trig.value(0)
    servo.duty_u16(0)
    servo.deinit()
    Pin(15, Pin.OUT, value=0)
    print('Scan finished; servo signal off')
