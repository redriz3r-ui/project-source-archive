"""MicroPython-friendly local effect plugins."""

import math
import random

WIDTH, HEIGHT = 53, 11
PALETTES = {
    "cyberpunk": ((5, 0, 24), (112, 32, 255), (0, 207, 255), (255, 60, 172)),
    "sunset": ((23, 0, 33), (255, 49, 88), (255, 140, 66), (255, 209, 102)),
    "ocean": ((0, 27, 58), (0, 102, 204), (0, 212, 255), (184, 243, 255)),
    "fire": ((8, 0, 0), (140, 18, 0), (255, 90, 0), (255, 224, 102)),
    "forest": ((0, 19, 8), (0, 107, 60), (61, 204, 116), (216, 255, 150)),
    "mono": ((0, 0, 0), (255, 255, 255)),
}


def color(value):
    if isinstance(value, str) and len(value) == 7:
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(value)


def palette(layer):
    value = layer.get("palette", "cyberpunk")
    return PALETTES.get(value, PALETTES["cyberpunk"]) if isinstance(value, str) else tuple(color(v) for v in value)


def put(buf, x, y, rgb, opacity=1, blend="alpha"):
    x, y = int(x), int(y)
    if x < 0 or x >= WIDTH or y < 0 or y >= HEIGHT: return
    i = (y * WIDTH + x) * 3
    for n in range(3):
        old, new = buf[i + n], int(rgb[n] * opacity)
        if blend == "add": buf[i + n] = min(255, old + new)
        elif blend == "max": buf[i + n] = max(old, new)
        elif blend == "replace": buf[i + n] = new
        else: buf[i + n] = int(old * (1 - opacity) + rgb[n] * opacity)


class Effect:
    def __init__(self, layer, seed=0):
        self.layer, self.colors = layer, palette(layer)
        self.speed = float(layer.get("speed", 1))
        self.intensity = float(layer.get("intensity", .5))
        self.opacity = float(layer.get("opacity", 1))
        self.blend = layer.get("blend", "alpha")
        self.seed = seed

    def dot(self, buf, x, y, rgb): put(buf, x, y, rgb, self.opacity, self.blend)


class Rain(Effect):
    def render(self, buf, t):
        for n in range(max(8, int(WIDTH * (.18 + self.intensity * .38)))):
            depth=1+n%3; travel=HEIGHT+3+depth*2
            y=int(t*self.speed*(4+depth*3)+n*5.7)%travel-4
            x=(n*23+n*n*3+int(t*self.speed*depth))%WIDTH
            rgb=self.colors[1+n%max(1,len(self.colors)-1)]
            for tail in range(1+depth):
                fade=1-tail/(2+depth)
                self.dot(buf,x-tail//2,y-tail,tuple(int(v*fade) for v in rgb))


class Snow(Effect):
    def render(self, buf, t):
        for n in range(max(2, int(WIDTH * (.05 + self.intensity * .18)))):
            y = int(t * self.speed * (1 + n % 2) + n * 5) % (HEIGHT + 2) - 1
            x = int(n * 13 + math.sin(t * self.speed + n) * 2) % WIDTH
            self.dot(buf, x, y, self.colors[-1])


class City(Effect):
    def render(self, buf, t):
        flicker=float(self.layer.get("window_flicker",.08))
        for x in range(WIDTH):
            h = 3 + ((x * 7 + x // 3) % 7)
            for y in range(HEIGHT - 1 - h, HEIGHT): self.dot(buf, x, y, self.colors[0])
            if x % 3 == 1:
                for y in range(HEIGHT - h, HEIGHT - 1, 2):
                    if ((x * 101 + y * 17 + int(t * self.speed/max(.02,flicker))) % 10) > 3: self.dot(buf, x, y, self.colors[-1])


class Stars(Effect):
    def render(self, buf, t):
        tick = int(t * self.speed * 5)
        for n in range(int(8 + self.intensity * 45)):
            x, y = (n * 37 + tick // 2) % WIDTH, (n * 17 + n // 2) % HEIGHT
            if (tick + n) % 3: self.dot(buf, x, y, self.colors[-1])


class Waves(Effect):
    def render(self, buf, t):
        for band in range(3):
            amplitude=.8+self.intensity*(2.7-band*.45)
            phase=t*self.speed*(2.4+band*.35)+band*1.8
            for x in range(WIDTH):
                y=5+band*1.5+math.sin(x*(.20+band*.025)+phase)*amplitude
                rgb=self.colors[(band+1)%len(self.colors)]; self.dot(buf,x,y,rgb)
                if band==0: self.dot(buf,x,y+1,tuple(v//3 for v in rgb))


class Scanner(Effect):
    def render(self, buf, t):
        p = int(t * self.speed * 16) % ((WIDTH - 1) * 2)
        x = p if p < WIDTH else (WIDTH - 1) * 2 - p
        for dx in range(-3, 4):
            rgb = tuple(int(c * (1 - abs(dx) / 4)) for c in self.colors[-1])
            for y in range(HEIGHT): self.dot(buf, x + dx, y, rgb)


class Field(Effect):
    kind = "plasma"
    def render(self, buf, t):
        tick = int(t * self.speed * 8)
        for y in range(HEIGHT):
            for x in range(WIDTH):
                if self.kind == "noise": index = (x * 13 + y * 7 + tick * 11) % len(self.colors)
                elif self.kind == "fire": index = min(len(self.colors)-1, int((HEIGHT-y)/HEIGHT*len(self.colors)))
                else: index = int(((math.sin(x*.25+t*self.speed)+math.sin(y*.65-t*self.speed*.7)+2)/4)*len(self.colors))
                self.dot(buf, x, y, self.colors[min(len(self.colors)-1, index)])
class Noise(Field): kind="noise"
class Fire(Effect):
    def render(self,buf,t):
        tick=int(t*self.speed*12)
        for x in range(WIDTH):
            wave=(math.sin(x*.48+t*self.speed*5)+1)*.5
            jitter=((x*97+tick//2)*17%101)/100
            height=2+int(self.intensity*7*(.6*wave+.4*jitter))
            for dy in range(height):
                index=min(len(self.colors)-1,int((height-dy)/max(1,height)*len(self.colors)))
                self.dot(buf,x,HEIGHT-1-dy,self.colors[index])
        for ember in range(int(2+self.intensity*7)):
            x=(ember*19+tick*3)%WIDTH; y=HEIGHT-4-((tick+ember*7)%8)
            self.dot(buf,x,y,self.colors[-1])
class Plasma(Field): kind="plasma"


class Comet(Effect):
    def render(self, buf, t):
        head = int(t * self.speed * 12) % (WIDTH + 12) - 6
        y = int(HEIGHT / 2 + math.sin(t * self.speed) * 3)
        for tail in range(12): self.dot(buf, head-tail, y, tuple(int(v*(1-tail/12)) for v in self.colors[-1]))


class Lightning(Effect):
    def render(self, buf, t):
        tick = int(t * self.speed * 5)
        if (tick * 17) % 100 > self.intensity * 22: return
        x = (tick * 31) % WIDTH
        for y in range(HEIGHT):
            x += ((tick + y * 7) % 3) - 1
            self.dot(buf, x, y, self.colors[-1])


class Heart(Effect):
    def render(self, buf, t):
        scale = 1 if math.sin(t*self.speed*5) > -.4 else .75
        for y in range(-5, 5):
            for x in range(-6, 7):
                nx, ny = x/(5*scale), -y/(5*scale)
                if (nx*nx+ny*ny-1)**3-nx*nx*ny**3 <= 0: self.dot(buf, WIDTH//2+x, 5+y, self.colors[-1])


class Eyes(Effect):
    def render(self, buf, t):
        cycle=(t*self.speed)%7; blink=5.55<cycle<5.82
        pupil=-3 if cycle<1.8 else 3 if 2.4<cycle<4.2 else 0
        iris=self.colors[-1]; white=tuple(max(70,min(255,v+105)) for v in iris)
        for center in (14,38):
            for x in range(center-9,center+10):
                dx=abs(x-center); half=1 if dx>7 else 2 if dx>5 else 3
                if blink:
                    self.dot(buf,x,5,iris)
                    if dx<7: self.dot(buf,x,6,tuple(v//4 for v in iris))
                else:
                    for y in range(5-half,6+half): self.dot(buf,x,y,white)
            if not blink:
                px=center+pupil
                for y in range(3,8):
                    for x in range(px-2,px+3):
                        if abs(x-px)+abs(y-5)<=3: self.dot(buf,x,y,iris)
                self.dot(buf,px,5,(0,0,0)); self.dot(buf,px-1,4,(255,255,255))


class Fireflies(Effect):
    def render(self,buf,t):
        for n in range(max(3,int(4+self.intensity*12))):
            x=(n*19+math.sin(t*self.speed*.7+n)*7)%WIDTH
            y=(n*5+math.cos(t*self.speed+n*2)*3)%HEIGHT
            pulse=(math.sin(t*4+n)+1)/2
            self.dot(buf,x,y,tuple(int(v*pulse) for v in self.colors[-1]))

class Particles(Effect):
    def render(self,buf,t):
        for n in range(max(8,int(10+self.intensity*24))):
            life=(t*self.speed*(.45+(n%5)*.08)+n*.173)%1; angle=n*2.399
            radius=life*(8+self.intensity*23)
            x=WIDTH/2+math.cos(angle)*radius; y=HEIGHT/2+math.sin(angle)*radius*.34
            rgb=self.colors[1+n%max(1,len(self.colors)-1)]
            self.dot(buf,x,y,tuple(int(v*(1-life)) for v in rgb))

class Spectrum(Effect):
    def render(self,buf,t):
        for bar in range(13):
            pulse=(math.sin(t*self.speed*(3.2+bar*.11)+bar*1.7)+1)*.5
            height=1+int(pulse*(2+self.intensity*8)); rgb=self.colors[1+bar%max(1,len(self.colors)-1)]
            x0=bar*4+1
            for x in range(x0,min(x0+3,WIDTH)):
                for y in range(HEIGHT-1,HEIGHT-1-height,-1): self.dot(buf,x,y,rgb)

FONT={" ":(0,0,0,0,0),"A":(30,5,5,30,0),"B":(31,21,21,10,0),"C":(14,17,17,10,0),
"D":(31,17,17,14,0),"E":(31,21,21,17,0),"F":(31,5,5,1,0),"G":(14,17,21,29,0),
"H":(31,4,4,31,0),"I":(17,31,17,0,0),"J":(8,16,16,15,0),"K":(31,4,10,17,0),
"L":(31,16,16,16,0),"M":(31,2,4,2,31),"N":(31,2,4,31,0),"O":(14,17,17,14,0),
"P":(31,5,5,2,0),"Q":(14,17,25,30,0),"R":(31,5,13,18,0),"S":(18,21,21,9,0),
"T":(1,1,31,1,1),"U":(15,16,16,15,0),"V":(7,8,16,8,7),"W":(31,8,4,8,31),
"X":(17,10,4,10,17),"Y":(1,2,28,2,1),"Z":(17,25,21,19,17),"0":(14,17,17,14,0),
"1":(18,31,16,0,0),"2":(25,21,21,18,0),"3":(17,21,21,10,0),"4":(7,4,4,31,4),
"5":(23,21,21,9,0),"6":(14,21,21,8,0),"7":(1,1,29,3,0),"8":(10,21,21,10,0),
"9":(2,21,21,14,0),"'":(3,0,0,0,0),"!":(23,0,0,0,0),":":(10,0,0,0,0),
"-":(4,4,4,0,0),".":(16,0,0,0,0)}


class Text(Effect):
    def render(self,buf,t):
        message=str(self.layer.get("text","")).upper()
        width=sum(len(FONT.get(ch,FONT[" "]))+1 for ch in message)
        x=WIDTH-int(t*self.speed*10)%max(1,WIDTH+width)
        for ch in message:
            columns=FONT.get(ch,FONT[" "])
            for dx,bits in enumerate(columns):
                for dy in range(5):
                    if bits&(1<<dy): self.dot(buf,x+dx,3+dy,self.colors[-1])
            x+=len(columns)+1


REGISTRY = {"rain":Rain,"snow":Snow,"fire":Fire,"plasma":Plasma,"noise":Noise,
 "stars":Stars,"fireflies":Fireflies,"particles":Particles,"comet":Comet,
 "waves":Waves,"scanner":Scanner,"city":City,"heart":Heart,"eyes":Eyes,
 "lightning":Lightning,"spectrum":Spectrum,"icon":Heart,"text":Text}


def create(layer, seed=0): return REGISTRY.get(layer.get("effect"), Stars)(layer, seed)
