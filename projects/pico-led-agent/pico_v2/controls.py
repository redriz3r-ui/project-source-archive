"""Debounced buttons and ambient brightness policy."""

try:
    from time import ticks_diff
except ImportError:
    def ticks_diff(a,b): return a-b


class Controls:
    def __init__(self, display, runtime, auto_brightness=True):
        self.display, self.runtime, self.auto = display, runtime, auto_brightness
        self.previous = {}
        self.last_light = 0

    def tick(self, now):
        actions = (("SWITCH_BRIGHTNESS_UP",.05),("SWITCH_BRIGHTNESS_DOWN",-.05))
        for name,delta in actions:
            state=self.display.pressed(name)
            if state and not self.previous.get(name): self.display.adjust_brightness(delta)
            self.previous[name]=state
        surprise=("plasma","comet","fireflies","scanner")[(now//1000)%4]
        button_effects=(("SWITCH_A","rain","ocean"),("SWITCH_B","fire","fire"),
                        ("SWITCH_C","eyes","cyberpunk"),("SWITCH_D",surprise,"sunset"))
        for name,effect,palette in button_effects:
            state=self.display.pressed(name)
            if state and not self.previous.get(name):
                scene={"v":2,"name":"button "+effect,"brightness":self.display.value,"loop":True,
                       "background":"#000000","steps":[{"duration":12,"layers":[{"effect":effect,"palette":palette}]}]}
                self.runtime.submit(scene,now)
            self.previous[name]=state
        sleep="SWITCH_SLEEP"; state=self.display.pressed(sleep)
        if state and not self.previous.get(sleep): self.runtime.stop(True)
        self.previous[sleep]=state
        if self.auto and ticks_diff(now,self.last_light)>=2000:
            raw=self.display.ambient_light()
            target=.04+(max(0,min(4095,raw))/4095)*.36
            self.display.set_brightness(self.display.value*.8+target*.2)
            self.last_light=now
