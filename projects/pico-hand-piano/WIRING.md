# Wiring reference

**Disconnect USB before changing wiring.** HC-SR04 ECHO must pass through the resistor divider before reaching the Pico. A direct 5V ECHO signal is unsafe for Pico GPIO.

There are two grids: the **Pico grid** holds the Pico; the **resistor grid** holds five 220-ohm resistors. On either grid, a–e in one numbered row connect together. f–j form a separate connected group across the centre gap.

## Five 220-ohm resistors on the resistor grid

| Resistor | First leg | Second leg |
|---|---|---|
| 1 | a10 | a12 |
| 2 | b12 | a14 |
| 3 | b14 | a16 |
| 4 | b16 | a18 |
| 5 | b18 | a20 |

Two resistors above the row-14 tap and three below it reduce nominal 5V ECHO to about 3V. Row 14 is signal, row 20 is ground, row 25 is 5V power.

## Exact electrical connections

| From | To |
|---|---|
| Sensor ECHO | Resistor-grid c10 |
| Resistor-grid c14 | Pico GP14, physical pin 19 |
| Resistor-grid c20 | Pico GND, physical pin 18 |
| Sensor GND | Resistor-grid d20 |
| Sensor TRIG | Pico GP13, physical pin 17 |
| Pico VBUS, physical pin 40 | Resistor-grid b25 |
| Sensor VCC | Resistor-grid c25 |
| Servo red power | Resistor-grid a25 |
| Servo brown ground | Pico GND, physical pin 38 |
| Servo orange signal | Pico GP15, physical pin 20 |

## Pico-grid coordinates — conditional on placement

These hole coordinates apply **only if the Pico’s topmost header pins are in breadboard row 3, with USB at the top**. Electrical pin names above take priority if the board is moved.

| Pico-grid hole | Pin | Connection |
|---|---|---|
| j3 | VBUS / physical 40 | Resistor-grid b25 |
| j5 | GND / physical 38 | Servo ground |
| a19 | GP13 / physical 17 | Sensor TRIG |
| a20 | GND / physical 18 | Resistor-grid c20 |
| a21 | GP14 / physical 19 | Resistor-grid c14 |
| a22 | GP15 / physical 20 | Servo signal |

Use printed sensor labels; jumper colour does not identify electrical function. Breadboard holes require metal pin ends. Insulate exposed extension joints from other wires. Keep the servo body secured and wires loose; unplug immediately if a servo stalls/buzzes continuously, the Pico resets, or anything heats up.
