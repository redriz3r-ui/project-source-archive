"""V2 USB runtime entry point. Wi-Fi server is optional and independently configured."""

import json, sys, time
try: import config
except ImportError:
    class config:
        BRIGHTNESS=.18; MAX_BRIGHTNESS=.60; AUTO_BRIGHTNESS=True; BUTTONS=True; FPS=15

from display import GalacticDisplay
from runtime import Runtime
from controls import Controls

initial_brightness=float(getattr(config,"BRIGHTNESS",.18))
if initial_brightness>1: initial_brightness/=15
display=GalacticDisplay(initial_brightness,getattr(config,"MAX_BRIGHTNESS",.60))
runtime=Runtime(display,getattr(config,"FPS",15),getattr(config,"SOUND_CUES",False))
controls=Controls(display,runtime,getattr(config,"AUTO_BRIGHTNESS",True))

wifi_server=None
if getattr(config,"WIFI_ENABLED",False):
    try:
        import network
        wlan=network.WLAN(network.STA_IF); wlan.active(True); wlan.connect(config.WIFI_SSID,config.WIFI_PASSWORD)
        deadline=time.ticks_add(time.ticks_ms(),15000)
        while not wlan.isconnected() and time.ticks_diff(deadline,time.ticks_ms())>0: time.sleep_ms(100)
        if wlan.isconnected():
            from wifi_server import WifiServer
            wifi_server=WifiServer(runtime,getattr(config,"HTTP_PORT",80),getattr(config,"API_TOKEN",""))
    except Exception: wifi_server=None

import select
poller=select.poll(); poller.register(sys.stdin,select.POLLIN)

watchdog=None
try:
    from machine import WDT
    watchdog=WDT(timeout=8000)
except Exception: pass

while True:
    now=time.ticks_ms()
    runtime.tick(now)
    if getattr(config,"BUTTONS",True): controls.tick(now)
    if wifi_server: wifi_server.poll(now)
    if watchdog: watchdog.feed()
    if poller.poll(0):
        line=sys.stdin.readline()
        if line:
            try: response=runtime.handle(json.loads(line),now)
            except Exception as exc: response={"ok":False,"error":str(exc)}
            print(json.dumps(response))
    time.sleep_ms(5)
