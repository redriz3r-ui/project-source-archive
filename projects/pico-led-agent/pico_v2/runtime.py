"""Protocol, queue, autonomous playback and frame receiver; hardware independent."""

try:
    import ubinascii as binascii
except ImportError:
    import binascii
import time

from effects import create, color, put, WIDTH, HEIGHT

EFFECT_NAMES = ("rain","snow","fire","plasma","noise","stars","fireflies","particles",
                "comet","waves","scanner","city","text","heart","eyes","lightning","spectrum","icon")


def now_ms():
    return time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.monotonic()*1000)


def diff_ms(a, b):
    return time.ticks_diff(a, b) if hasattr(time, "ticks_diff") else a-b


def add_ms(value,delta):
    return time.ticks_add(value,delta) if hasattr(time,"ticks_add") else value+delta


class Runtime:
    def __init__(self, display, fps=15, sound_cues=False):
        self.display, self.fps = display, max(5, min(30, int(fps)))
        self.active = None
        self.started = 0
        self.paused = []
        self.queue = []
        self.frame = bytearray(WIDTH*HEIGHT*3)
        self.effects = []
        self.step_effects = []
        self.sequence = 0
        self.last_frame = 0
        self.mode = "idle"
        self.last_error = None
        self.sound_cues = sound_cues

    def handle(self, msg, now=None):
        now = now_ms() if now is None else now
        request_id = msg.get("id")
        try:
            if msg.get("v") == 1:
                result = self._handle_v1(msg, now)
                if request_id is not None: result["id"] = request_id
                return result
            if msg.get("v") != 2: raise ValueError("unsupported protocol version")
            cmd = msg.get("cmd")
            if cmd == "capabilities": result = self.capabilities()
            elif cmd == "status": result = self.status(now)
            elif cmd == "scene":
                scene = validate_scene(msg.get("scene"))
                self.submit(scene, now)
                result = {"ok":True,"message":"accepted scene","scene":scene.get("name")}
            elif cmd == "frame":
                self.accept_frame(msg)
                result = {"ok":True,"message":"frame displayed"}
            elif cmd == "stop": self.stop(False); result={"ok":True,"message":"stopped"}
            elif cmd == "clear": self.stop(True); result={"ok":True,"message":"cleared"}
            elif cmd == "brightness":
                self.display.set_brightness(float(msg.get("value")))
                result={"ok":True,"message":"brightness updated"}
            else: raise ValueError("unknown command")
        except Exception as exc:
            self.last_error = str(exc)
            result = {"ok":False,"error":str(exc)}
        if request_id is not None: result["id"] = request_id
        return result

    def _handle_v1(self,msg,now):
        cmd=msg.get("cmd")
        if cmd=="ping": return {"ok":True,"message":"pico v2 ready","animation":self.active.get("name") if self.active else None}
        if cmd=="setting":
            if msg.get("name")=="brightness": self.display.set_brightness(float(msg.get("value",3))/15)
            else: raise ValueError("unsupported v1 setting")
            return {"ok":True,"message":"updated "+msg.get("name")}
        if cmd in ("stop","clear"):
            self.stop(cmd=="clear"); return {"ok":True,"message":"cleared" if cmd=="clear" else "stopped"}
        if cmd=="scroll": effect={"effect":"text","text":str(msg.get("text",""))[:80],"palette":["#000000","#00ddff"],"speed":msg.get("params",{}).get("speed",1)}
        elif cmd=="play":
            name=msg.get("animation"); mapped={"twinkle":"stars"}.get(name,name)
            if mapped not in EFFECT_NAMES: raise ValueError("unknown animation")
            effect={"effect":mapped,"palette":"cyberpunk","speed":msg.get("params",{}).get("speed",1)}
        else: raise ValueError("unknown command")
        scene={"v":2,"name":"v1 "+cmd,"brightness":self.display.value,"loop":True,"background":"#000000","steps":[{"duration":10,"layers":[effect]}]}
        self.submit(validate_scene(scene),now)
        return {"ok":True,"message":"playing "+effect["effect"]}

    def capabilities(self):
        return {"ok":True,"protocols":[1,2],"width":WIDTH,"height":HEIGHT,"fps":self.fps,
                "effects":list(EFFECT_NAMES),"transitions":["cut","fade","wipe","dissolve","glitch"],
                "blends":["replace","alpha","add","max"],
                "features":["rgb","scenes","layers","queue","resume","rle-frames","buttons","ambient-light","watchdog"]}

    def status(self, now=None):
        return {"ok":True,"mode":self.mode,"scene":self.active.get("name") if self.active else None,
                "queue":len(self.queue),"paused":len(self.paused),"brightness":self.display.value,
                "last_error":self.last_error,"uptime_in_scene":diff_ms(now or now_ms(),self.started)/1000 if self.active else 0}

    def submit(self, scene, now):
        expires=float(scene.get("expires_in",0) or 0)
        if expires: scene["_expires_at"]=add_ms(now,int(expires*1000))
        priority = int(scene.get("priority",0))
        if self.active is None or priority >= int(self.active.get("priority",0)):
            if self.active and priority > int(self.active.get("priority",0)):
                self.paused.append((self.active, diff_ms(now,self.started)))
            self._start(scene, now)
        else:
            self.sequence += 1
            self.queue.append((-priority,self.sequence,scene))
            self.queue.sort(key=lambda item:(item[0],item[1]))

    def _start(self, scene, now, elapsed=0):
        self.active, self.started, self.mode = scene, now-elapsed, "scene"
        self.step_effects=[[create(layer,index*101+n) for n,layer in enumerate(step["layers"])] for index,step in enumerate(scene["steps"])]
        self._prepare_step(0)
        self.display.set_brightness(float(scene.get("brightness",.2)))
        if self.sound_cues:
            try: self.display.cue(660)
            except Exception: pass

    def _prepare_step(self, index):
        self.effects = self.step_effects[index]

    def tick(self, now=None):
        now = now_ms() if now is None else now
        if self.mode != "scene" or not self.active: return False
        expires=self.active.get("_expires_at")
        if expires is not None and diff_ms(now,expires)>=0:
            self._next(now); return False
        if diff_ms(now,self.last_frame) < 1000//self.fps: return False
        elapsed = diff_ms(now,self.started)/1000
        total = sum(float(step.get("duration",10)) for step in self.active["steps"])
        if elapsed >= total:
            if self.active.get("loop",True): self.started=now; elapsed=0
            else: self._next(now); return False
        offset, index = 0, 0
        for n,step in enumerate(self.active["steps"]):
            if elapsed < offset+float(step.get("duration",10)): index=n; break
            offset += float(step.get("duration",10))
        marker = self.active.get("_step")
        if marker != index:
            self.active["_step"] = index
            self._prepare_step(index)
        local=elapsed-offset
        self._render_step(index,local,self.frame)
        transition=self.active.get("transition",{})
        duration=float(transition.get("duration",0))
        if index>0 and duration>0 and local<duration:
            previous=bytearray(len(self.frame))
            self._render_step(index-1,float(self.active["steps"][index-1].get("duration",10)),previous)
            self._transition(previous,self.frame,local/duration,transition.get("type","cut"))
        self.display.show(self.frame)
        self.last_frame=now
        return True

    def _render_step(self,index,local,target):
        bg=color(self.active.get("background","#000000")); target[:]=bytes(bg)*(WIDTH*HEIGHT)
        for effect in self.step_effects[index]: effect.render(target,local)

    def _transition(self,previous,current,progress,kind):
        progress=max(0,min(1,progress))
        if kind=="cut": return
        if kind=="fade":
            for i in range(len(current)): current[i]=int(previous[i]*(1-progress)+current[i]*progress)
        elif kind=="wipe":
            edge=int(WIDTH*progress)
            for y in range(HEIGHT):
                for x in range(edge,WIDTH):
                    i=(y*WIDTH+x)*3; current[i:i+3]=previous[i:i+3]
        elif kind=="dissolve":
            threshold=int(progress*100)
            for y in range(HEIGHT):
                for x in range(WIDTH):
                    if (x*91+y*37)%100>=threshold:
                        i=(y*WIDTH+x)*3; current[i:i+3]=previous[i:i+3]
        elif kind=="glitch":
            amount=int((1-progress)*8)
            if amount:
                copy=bytes(current)
                for y in range(0,HEIGHT,3):
                    shift=(y*7+int(progress*100))%(amount*2+1)-amount
                    for x in range(WIDTH):
                        sx=max(0,min(WIDTH-1,x+shift)); si=(y*WIDTH+sx)*3; di=(y*WIDTH+x)*3
                        current[di:di+3]=copy[si:si+3]

    def _next(self, now):
        scene=None; elapsed=0
        while self.paused and scene is None:
            candidate,candidate_elapsed=self.paused.pop()
            expiry=candidate.get("_expires_at")
            if expiry is None or diff_ms(now,expiry)<0: scene,elapsed=candidate,candidate_elapsed
        if scene is not None:
            self._start(scene,now,elapsed)
        elif self.queue:
            scene=None
            while self.queue and scene is None:
                _,_,candidate=self.queue.pop(0)
                expiry=candidate.get("_expires_at")
                if expiry is None or diff_ms(now,expiry)<0: scene=candidate
            if scene is not None: self._start(scene,now)
            else: self.stop(False)
        else: self.stop(False)

    def accept_frame(self,msg):
        if msg.get("encoding")!="rgb-rle-base64" or msg.get("width")!=WIDTH or msg.get("height")!=HEIGHT: raise ValueError("unsupported frame format")
        raw=binascii.a2b_base64(msg.get("data", "")); out=bytearray()
        if len(raw)%4: raise ValueError("invalid RLE payload")
        for i in range(0,len(raw),4):
            count=raw[i]
            if not count: raise ValueError("zero RLE run")
            out.extend(bytes(raw[i+1:i+4])*count)
            if len(out)>len(self.frame): raise ValueError("frame overflow")
        if len(out)!=len(self.frame): raise ValueError("incomplete frame")
        self.frame[:]=out; self.display.show(self.frame); self.mode="frame"

    def stop(self, clear):
        self.active=None; self.effects=[]; self.step_effects=[]; self.queue=[]; self.paused=[]; self.mode="idle"
        if clear: self.display.clear()


def validate_scene(scene):
    if not isinstance(scene,dict) or scene.get("v")!=2: raise ValueError("invalid scene")
    steps=scene.get("steps")
    if not isinstance(steps,list) or not 1<=len(steps)<=32: raise ValueError("invalid steps")
    brightness=float(scene.get("brightness",.2))
    if brightness<0 or brightness>1: raise ValueError("invalid brightness")
    transition=scene.get("transition",{"type":"cut","duration":0})
    if transition.get("type","cut") not in ("cut","fade","wipe","dissolve","glitch"): raise ValueError("invalid transition")
    for step in steps:
        layers=step.get("layers")
        if not isinstance(layers,list) or not 1<=len(layers)<=16: raise ValueError("invalid layers")
        for layer in layers:
            if layer.get("effect") not in EFFECT_NAMES: raise ValueError("unknown effect")
            speed=float(layer.get("speed",1)); intensity=float(layer.get("intensity",.5))
            if speed<.05 or speed>8 or intensity<0 or intensity>1: raise ValueError("invalid effect parameters")
    return scene
