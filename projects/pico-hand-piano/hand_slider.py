import glob
from collections import deque
from statistics import median
import queue
import threading
import time
import tkinter as tk
import serial
from song_player import SongPlayer, COUNT

root = tk.Tk()
root.title('Pico • Summer Means New Love')
root.geometry('820x720')
root.configure(bg='#101820')
root.minsize(640, 580)
updates = queue.Queue()
stop = threading.Event()
active = False
closing = False
NEAR, FAR = 2.0, 20.0
level = None
target = None
shown = None
BG, FG, ACCENT = '#101820', '#edf5f8', '#57e3ac'

def text(value, size, color=FG):
    w = tk.Label(root, text=value, font=('Helvetica', size), bg=BG, fg=color)
    w.pack(pady=8)
    return w
text('Summer Means New Love', 26)
text('Farther away ↑  •  Closer ↓', 13, '#9db0bd')
value_label = text('—', 34)
distance_label = text('Waiting for your hand', 13)
note_label = text('Up: play forward • down: play backward • hold: quiet', 13, ACCENT)
player = SongPlayer()
sound_enabled = tk.BooleanVar(value=True)
volume = tk.DoubleVar(value=45)
tempo = tk.DoubleVar(value=125)
canvas = tk.Canvas(root, width=360, height=350, bg=BG, highlightthickness=0)
canvas.pack(expand=True, fill='both', padx=24)
status = text('Click Start with the sensor facing your palm.', 11, '#9db0bd')
text('Opening phrase • 2–20 inches • your movement sets the rhythm', 11, '#9db0bd')
frame = tk.Frame(root, bg=BG)
frame.pack(pady=(8, 20))

CODE = b'''from machine import Pin, PWM, time_pulse_us
from time import sleep_ms, sleep_us
p = PWM(Pin(15)); p.duty_u16(0); p.deinit(); Pin(15, Pin.OUT, value=0)
t = Pin(13, Pin.OUT, value=0)
e = Pin(14, Pin.IN)
try:
    while True:
        t.value(0); sleep_us(2); t.value(1); sleep_us(10); t.value(0)
        duration = time_pulse_us(e, 1, 30000)
        print("HAND", duration)
        sleep_ms(70)
finally:
    t.value(0)
    Pin(15, Pin.OUT, value=0)
    print("HAND_STOPPED")
'''

last_value = None

def draw(value=None):
    global last_value
    last_value = value
    canvas.delete('all')
    w, h = max(320, canvas.winfo_width()), max(240, canvas.winfo_height())
    x, top, bottom = w/2, 35, h-35
    canvas.create_line(x, top, x, bottom, fill='#30434f', width=32)
    canvas.create_text(x+55, top, text='Last note', fill=FG, anchor='w')
    canvas.create_text(x+55, bottom, text='First note', fill=FG, anchor='w')
    for tick in range(1, COUNT-1):
        ty = bottom - (bottom-top)*tick/(COUNT-1)
        canvas.create_line(x-27, ty, x+27, ty, fill='#30434f', width=2)
    if value is not None:
        y = bottom - (bottom-top)*value/100
        canvas.create_line(x, y, x, bottom, fill=ACCENT, width=32)
        canvas.create_oval(x-24, y-24, x+24, y+24, fill=ACCENT, outline=BG, width=3)
    else:
        canvas.create_text(x-60, h/2, text='No\nreading', fill='#9db0bd', anchor='e')
canvas.bind('<Configure>', lambda event: draw(last_value))


def worker():
    s = None
    try:
        ports = glob.glob('/dev/cu.usbmodem*')
        if len(ports) != 1:
            raise RuntimeError('Connect one Pico by USB, then click Start.')
        s = serial.Serial(ports[0], 115200, timeout=.1, write_timeout=2)
        s.write(b'\r\x03\x03'); time.sleep(.3); s.read(8192)
        s.write(b'\x01'); time.sleep(.2)
        if b'raw REPL' not in s.read(8192):
            raise RuntimeError('Pico connection unavailable. Stop the other scanner first.')
        for offset in range(0, len(CODE), 256):
            s.write(CODE[offset:offset+256]); time.sleep(.01)
        s.write(b'\x04')
        buffer = b''
        last_response = time.monotonic()
        smooth = None
        samples = deque(maxlen=3)
        last_valid = 0.0
        while not stop.is_set():
            chunk = s.read(min(256, s.in_waiting or 1))
            buffer += chunk
            if chunk:
                last_response = time.monotonic()
            if time.monotonic()-last_response > 3:
                raise RuntimeError('Pico stopped responding. Check its USB connection.')
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                line = line.decode(errors='replace').strip()
                if 'HAND ' in line:
                    pulse = int(line.split('HAND ')[1])
                    inches = pulse * .0343 / 2 / 2.54 if pulse > 0 else None
                    if inches is None or not 1 <= inches <= FAR + 2:
                        # Briefly hold through missed echoes rather than flashing.
                        if time.monotonic() - last_valid > .5:
                            smooth = None
                            samples.clear()
                            updates.put(('reading', None))
                    else:
                        last_valid = time.monotonic()
                        samples.append(inches)
                        filtered = median(samples)
                        # Reject isolated spikes; follow sustained hand movements.
                        smooth = filtered if smooth is None else .3*filtered + .7*smooth
                        updates.put(('reading', smooth))
                elif 'Traceback' in line:
                    raise RuntimeError('Pico program stopped. Click Start to reconnect.')
        updates.put(('status', 'Stopped • servo signal off'))
    except Exception as exc:
        updates.put(('status', str(exc)))
    finally:
        if s:
            try:
                s.write(b'\x03\x03'); time.sleep(.25); s.read(8192); s.write(b'\x02')
            except Exception:
                pass
            s.close()
        updates.put(('idle', None))


def start():
    global active, target, shown, level
    if active or closing:
        return
    player.clear()
    active = True
    target = shown = level = None
    draw()
    stop.clear()
    start_button.configure(state='disabled')
    stop_button.configure(state='normal')
    status.configure(text='Running • hold your palm in front of both sensor eyes')
    threading.Thread(target=worker, daemon=True).start()


def halt():
    player.clear()
    stop.set()
    status.configure(text='Stopping…')


def close():
    global closing
    closing = True
    player.clear()
    if active:
        halt()
    else:
        root.destroy()


def poll():
    global active, target, shown, level
    try:
        while True:
            kind, value = updates.get_nowait()
            if kind == 'reading':
                if value is None:
                    player.clear()
                    target = shown = level = None
                    value_label.configure(text='—')
                    distance_label.configure(text='No hand in range')
                    draw()
                else:
                    position = max(0, min(COUNT-1, (value-NEAR)/(FAR-NEAR)*(COUNT-1)))
                    # Separate sensor distance from the discrete control scale.
                    # Switch only past a midpoint plus a small hysteresis buffer.
                    if level is None or position > level + .65 or position < level - .65:
                        previous = level
                        level = min(COUNT-1, max(0, int(position + .5)))
                        if sound_enabled.get():
                            player.set_level(level)
                    player.set_level(level)
                    target = level/(COUNT-1)*100
                    if shown is None:
                        shown = target
            elif kind == 'status':
                status.configure(text=value)
            elif kind == 'idle':
                player.clear()
                active = False
                start_button.configure(state='normal')
                stop_button.configure(state='disabled')
    except queue.Empty:
        pass
    try:
        note = player.tick(sound_enabled.get(), volume.get(), tempo.get())
        if note:
            note_label.configure(text=note)
    except OSError:
        player.clear()
        sound_enabled.set(False)
        note_label.configure(text='Audio unavailable; slider still works')
    if target is not None:
        shown += (target-shown) * .22
        if abs(target-shown) < .03:
            shown = target
        value_label.configure(text=f'Note {level+1} / {COUNT}')
        distance_label.configure(text='Opening lead • move back to retrace')
        draw(shown)
    if closing and not active:
        root.destroy()
    else:
        root.after(20, poll)

start_button = tk.Button(frame, text='Start', command=start, font=('Helvetica', 13), padx=24, pady=8)
start_button.pack(side='left', padx=8)
stop_button = tk.Button(frame, text='Stop', command=halt, font=('Helvetica', 13), padx=24, pady=8, state='disabled')
stop_button.pack(side='left', padx=8)
tk.Checkbutton(frame, text='Sound', variable=sound_enabled, command=lambda: player.clear() if not sound_enabled.get() else player.set_level(level) if level is not None and active else None, bg=BG, fg=FG, selectcolor=BG, activebackground=BG, activeforeground=FG).pack(side='left', padx=12)
tk.Scale(frame, from_=0, to=100, orient='horizontal', variable=volume, label='Volume', bg=BG, fg=FG, highlightthickness=0, length=150).pack(side='left', padx=8)
tk.Scale(frame, from_=70, to=180, orient='horizontal', variable=tempo, label='Playback speed', bg=BG, fg=FG, highlightthickness=0, length=150).pack(side='left', padx=8)
root.protocol('WM_DELETE_WINDOW', close)
root.after(20, poll)
root.mainloop()
