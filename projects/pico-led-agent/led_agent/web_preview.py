"""Generate an interactive browser preview from the production scene renderer."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from .renderer import SceneRenderer


def build_preview(scene, path, fps=12, seconds=None):
    renderer=SceneRenderer(scene); fps=max(2,min(30,int(fps)))
    seconds=min(20,float(seconds if seconds is not None else renderer.total_duration))
    frames=[base64.b64encode(renderer.render(n/fps).pixels).decode() for n in range(max(1,int(seconds*fps)))]
    payload=json.dumps(frames,separators=(",",":")); title=json.dumps(renderer.scene["name"])
    html=f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Galactic preview</title><style>
:root{{color-scheme:dark}}body{{margin:0;background:#09080d;color:#eee;font:15px system-ui;display:grid;place-items:center;min-height:100vh}}
main{{width:min(94vw,1100px)}}h1{{font-size:18px;font-weight:500}}canvas{{width:100%;image-rendering:pixelated;background:#000;border-radius:8px}}
.controls{{display:flex;gap:12px;align-items:center;margin-top:14px}}button{{font:inherit;padding:7px 14px}}input{{flex:1}}
</style></head><body><main><h1 id="title"></h1><canvas width="53" height="11" aria-label="53 by 11 LED scene preview"></canvas>
<div class="controls"><button id="toggle">Pause</button><input id="scrub" type="range" min="0" max="{len(frames)-1}" value="0" aria-label="Frame"><span id="counter"></span></div>
</main><script>
const frames={payload}, fps={fps}, title={title}; document.getElementById('title').textContent=title;
const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d'),image=ctx.createImageData(53,11),scrub=document.getElementById('scrub'),counter=document.getElementById('counter');
let index=0,playing=true,last=0;
function draw(n){{const raw=atob(frames[n]);for(let p=0,i=0;p<raw.length;p+=3,i+=4){{image.data[i]=raw.charCodeAt(p);image.data[i+1]=raw.charCodeAt(p+1);image.data[i+2]=raw.charCodeAt(p+2);image.data[i+3]=255}}ctx.putImageData(image,0,0);scrub.value=n;counter.textContent=`${{n+1}} / ${{frames.length}}`;}}
function animate(now){{if(playing&&now-last>=1000/fps){{index=(index+1)%frames.length;draw(index);last=now}}requestAnimationFrame(animate)}}
document.getElementById('toggle').onclick=e=>{{playing=!playing;e.target.textContent=playing?'Pause':'Play'}};
scrub.oninput=()=>{{index=Number(scrub.value);draw(index)}};draw(0);requestAnimationFrame(animate);
</script></body></html>'''
    output=Path(path); output.parent.mkdir(parents=True,exist_ok=True); output.write_text(html,encoding="utf-8")
    return output

