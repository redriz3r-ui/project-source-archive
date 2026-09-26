from __future__ import annotations
import re
from pathlib import Path
from .utils import LOG, fingerprint, probe, rate, read_json, run, signature, write_json


def ingest(source: Path, root: Path, cfg: dict) -> Path:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise ValueError(f'Input video not found: {source}')
    metadata = probe(source)
    videos = [s for s in metadata['streams'] if s['codec_type'] == 'video' and not s.get('disposition', {}).get('attached_pic')]
    if not videos:
        raise ValueError('Input has no video stream')
    stream = videos[0]
    duration = float(stream.get('duration') or metadata['format'].get('duration', 0))
    if duration <= 0:
        raise ValueError('Input has no usable duration')
    identity = fingerprint(source)
    name = re.sub(r'[^\w-]+', '-', source.stem).strip('-') or 'film'
    project = root / f'{name}-{signature(identity)[:10]}'
    for folder in ('source', 'proxy', 'analysis/frames', 'analysis/shot_cache', 'analysis/semantic_cache', 'thumbnails', 'reel_plans', 'previews', 'exports'):
        (project / folder).mkdir(parents=True, exist_ok=True)
    proxy = project / 'proxy/analysis.mp4'
    proxy_options = {'source': identity, 'width': cfg['analysis']['proxy_width'], 'fps': cfg['analysis']['proxy_fps']}
    if stream.get('sample_aspect_ratio', '1:1') not in ('1:1', 'N/A', '0:1'):
        proxy_options['sample_aspect_ratio'] = stream['sample_aspect_ratio']
    proxy_key = signature(proxy_options)
    existing = read_json(project / 'analysis/film.json') if (project / 'analysis/film.json').exists() else {}
    if not proxy.exists() or existing.get('proxy_key') != proxy_key:
        LOG.info('[INGEST] %.1f minutes; creating analysis proxy', duration / 60)
        temp = proxy.with_name('analysis.partial.mp4')
        run(['ffmpeg', '-y', '-v', 'error', '-i', str(source), '-map', f'0:{stream["index"]}', '-map', '0:a:0?',
             '-vf', f"scale=w='trunc(min({int(cfg['analysis']['proxy_width'])},iw*sar)/2)*2':h='trunc(ow/dar/2)*2',setsar=1,fps={cfg['analysis']['proxy_fps']}",
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '25', '-threads', str(cfg['export']['threads']),
             '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', str(temp)])
        temp.replace(proxy)
    else:
        LOG.info('[INGEST] Reusing existing proxy')
    proxy_video = next(s for s in probe(proxy)['streams'] if s['codec_type'] == 'video')
    film = {'schema_version': 1, 'source': str(source), 'fingerprint': identity, 'duration': duration,
            'width': stream['width'], 'height': stream['height'], 'fps': rate(stream['avg_frame_rate']),
            'aspect_ratio': stream.get('display_aspect_ratio', f"{stream['width']}:{stream['height']}"),
            'video_codec': stream['codec_name'], 'video_stream_index': stream['index'],
            'audio_streams': [s for s in metadata['streams'] if s['codec_type'] == 'audio'],
            'proxy': str(proxy.resolve()), 'proxy_key': proxy_key,
            'proxy_width': proxy_video['width'], 'proxy_height': proxy_video['height'], 'ffprobe': metadata}
    write_json(project / 'analysis/film.json', film)
    write_json(project / 'source/source.json', {'original': str(source), 'policy': 'Referenced in place; never modified or copied.'})
    write_json(root / '.active.json', {'project': project.name})
    LOG.info('[INGEST] Project %s', project.name)
    return project
