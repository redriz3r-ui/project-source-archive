from collections import deque
from pathlib import Path
import json, subprocess, time
NOTES = json.loads((Path(__file__).resolve().parent / 'opening_lead.json').read_text())['notes']
COUNT = len(NOTES)
class SongPlayer:
    def __init__(self):
        self.level=None; self.pending=deque(); self.processes=[]; self.next_note=0; self.direction=0
        self.folder=Path(__file__).resolve().parent / 'song_piano'
    def set_level(self, level):
        if level is None: self.clear(); return
        if self.level is None: self.pending.append(level)
        elif level!=self.level:
            direction=1 if level>self.level else -1
            if self.direction and direction!=self.direction:
                self.pending.clear(); self.next_note=0
            self.direction=direction
            self.pending.extend(range(self.level+direction,level+direction,direction))
        self.level=level
    def tick(self, enabled, volume, speed=125):
        self.processes=[p for p in self.processes if p.poll() is None]
        if not enabled: self.clear(); return None
        if not self.pending or time.monotonic()<self.next_note: return None
        index=self.pending.popleft(); midi=NOTES[index]['midi']
        while len(self.processes)>=8: self.processes.pop(0).terminate()
        self.processes.append(subprocess.Popen(['/usr/bin/afplay','-v',str(volume/100),str(self.folder/f'{midi}.wav')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
        self.next_note=time.monotonic()+60/max(70,min(180,speed))/4
        name=('C','C♯','D','E♭','E','F','F♯','G','A♭','A','B♭','B')[midi%12]+str(midi//12-1)
        return f'Note {index+1}/{COUNT} • {name}'
    def clear(self):
        self.level=None; self.pending.clear(); self.direction=0; self.next_note=0
        for p in self.processes:
            if p.poll() is None: p.terminate()
        self.processes.clear()
