"""Run python tests/integration.py; uses generated footage, never the real film."""
import copy
import json
import logging
from pathlib import Path
import sys
import tempfile
import wave
import cv2
import numpy as np
import yaml
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reel import main
from src.utils import active_project, config, probe, read_json, run, write_json


def fixture(directory):
    silent=directory/'synthetic silent video.mp4'
    writer=cv2.VideoWriter(str(silent),cv2.VideoWriter_fourcc(*'mp4v'),24,(320,180))
    assert writer.isOpened()
    colors=[(20,30,210),(20,210,30),(210,30,20),(30,210,210),(210,20,210),
            (210,210,20),(90,60,200),(60,160,90),(160,60,90),(60,120,210)]
    for shot,color in enumerate(colors):
        for frame_id in range(72):
            frame=np.full((180,320,3),color,dtype=np.uint8)
            cv2.circle(frame,(40+frame_id*3,80),25,(240,240,240),-1)
            cv2.putText(frame,f'SHOT {shot+1}',(80,160),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,0,0),2)
            writer.write(frame)
    writer.release()
    target=directory/"new film ' with spaces.mp4"
    run(['ffmpeg','-y','-v','error','-i',str(silent),'-f','lavfi','-i','aevalsrc=0.5*sin(2*PI*(220*t+12*t*t)):s=48000:d=30',
         '-c:v','copy','-c:a','aac','-shortest',str(target)])
    return target


def decode_audio(source, output):
    run(['ffmpeg','-y','-v','error','-i',str(source),'-vn','-ar','48000','-ac','1','-c:a','pcm_s16le',str(output)])
    with wave.open(str(output),'rb') as reader:
        return np.frombuffer(reader.readframes(reader.getnframes()),dtype=np.int16).astype(np.float32)


def verify_audio_alignment(source, output, plan, shots, directory):
    original = decode_audio(source,directory/'reference.wav')
    rendered = decode_audio(output,directory/'rendered.wav')
    lookup = {s['shot_id']:s for s in shots}
    cursor = 0
    offsets = []
    for edit in plan['shots']:
        # Chirp timing identifies each selected source interval independently.
        midpoint = edit['duration'] / 2
        source_sample = round((lookup[edit['shot_id']]['start'] + edit['source_in'] + midpoint)*48000)
        output_sample = cursor + round(midpoint*48000)
        template = original[source_sample:source_sample+2048]
        search = rendered[output_sample-1600:output_sample+2048+1600]
        match = cv2.matchTemplate(search.reshape(1,-1),template.reshape(1,-1),cv2.TM_CCOEFF_NORMED)
        lag = int(np.argmax(match))-1600
        assert abs(lag) <= 80, f'Audio timing error {lag} samples'
        assert float(match.max()) > .9, f'Audio correlation too low: {match.max()}'
        offsets.append(lag)
        cursor += round(edit['duration']*30)*1600
    return offsets


def integration():
    logging.basicConfig(level=logging.INFO,format='%(message)s')
    with tempfile.TemporaryDirectory(prefix='reel integration ') as tmp:
        directory=Path(tmp)
        source=fixture(directory)
        cfg=config()
        cfg['export'].update(width=180,height=320,preset='ultrafast',crf=26)
        cfg['preview']['width']=90
        cfg_path=directory/'config.yaml'
        cfg_path.write_text(yaml.safe_dump(cfg))
        root=directory/'projects'
        common=['--config',str(cfg_path),'--projects-dir',str(root)]
        def cli(*args):
            result=main(common+list(args))
            assert result==0,(args,result)
        cli('ingest',str(source))
        project=active_project(root,None)
        proxy=Path(read_json(project/'analysis/film.json')['proxy'])
        before=proxy.stat().st_mtime_ns
        cli('ingest',str(source))
        assert proxy.stat().st_mtime_ns==before
        cli('analyze')
        shots=read_json(project/'analysis/shots.json')['shots']
        assert 9<=len(shots)<=11,f'Unexpected cut count {len(shots)}'
        checkpoints={p:p.stat().st_mtime_ns for p in (project/'analysis/shot_cache').glob('*.json')}
        cli('analyze')
        assert all(p.stat().st_mtime_ns==stamp for p,stamp in checkpoints.items())
        cli('generate','--mood','dark tense mysterious','--duration','6','--variants','3','--audio','original')
        for index in range(1,4):
            video=project/'exports'/f'reel_{index:03d}.mp4'
            run(['ffmpeg','-v','error','-i',str(video),'-f','null','-'])
            report=read_json(video.with_suffix('.json'))['verification']
            assert report['frames']==180 and report['width']==180 and report['height']==320
            assert abs(report['audio_duration']-report['video_duration'])<=1/30
        alignment = verify_audio_alignment(source,project/'exports/reel_001.mp4',read_json(project/'reel_plans/reel_001.json'),shots,directory)
        plan_path=project/'reel_plans/reel_001.json'
        plan=read_json(plan_path)
        modes=['smart_crop','fit','letterbox','blur_background','auto']
        plan['shots']=[{**copy.deepcopy(plan['shots'][i%len(plan['shots'])]),'duration':.5,'source_in':.25,'crop_mode':mode} for i,mode in enumerate(modes)]
        plan['end_card']={'enabled':True,'duration':1,'lines':['A TEST FILM','Tomorrow — 8 PM']}
        write_json(plan_path,plan)
        cli('preview','reel_001')
        cli('render','reel_001')
        cache_stamp=(project/'exports/reel_001.mp4').stat().st_mtime_ns
        cli('render','reel_001')
        assert cache_stamp==(project/'exports/reel_001.mp4').stat().st_mtime_ns
        cli('lock-shot','reel_001','1')
        locked=read_json(plan_path)['shots'][0]
        cli('regenerate','reel_001')
        assert read_json(plan_path)['shots'][0]==locked
        cli('set-crop','reel_001','2','smart_crop','--center','.75','.5')
        cli('set-duration','reel_001','2','.4')
        cli('reorder','reel_001','5','4','3','2','1')
        cli('remove-shot','reel_001','2')
        cli('replace-shot','reel_001','2',str(shots[-1]['shot_id']))
        cli('render','reel_001')
        cli('ingest',str(directory/'synthetic silent video.mp4'))
        cli('analyze')
        cli('generate','--mood','quiet','--duration','3','--aspect','1:1','--audio','original')
        silent_project=active_project(root,None)
        assert read_json(silent_project/'exports/reel_001.json')['verification']['audio_duration']==3
        cli('generate','--duration','3','--audio','muted')
        assert not any(s['codec_type']=='audio' for s in probe(silent_project/'exports/reel_002.mp4')['streams'])
        cli('generate','--duration','3','--audio','music','--music',str(source),'--audio-volume','0.5')
        assert read_json(silent_project/'reel_plans/reel_003.json')['audio_volume']==0.5
        assert read_json(silent_project/'exports/reel_003.json')['verification']['audio_duration']==3
        return {'status':'passed','detected_shots':len(shots),'audio_alignment_samples':alignment,'tests':['new-film CLI pipeline','three variants',
                'original audio waveform alignment','silent source','muted mode','music volume','frame counts','full decode','all framing modes',
                'preview','end card','cache reuse','locked regeneration','manual editing','spaces and apostrophe in paths']}

if __name__=='__main__':
    print(json.dumps(integration(),indent=2))
