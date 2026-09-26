"""FFmpeg rendering; integer-frame video and continuous PCM audio before AAC mux."""
from __future__ import annotations
from pathlib import Path
import tempfile
import wave
from .end_cards import draw_card
from .reel_director import validate_plan
from .reframer import crop_track, filter_graph
from .utils import LOG, aspect, even, fingerprint, probe, read_json, run, signature, validate_source, write_json

AUDIO_RATE = 48000


def silence(path: Path, samples: int) -> None:
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(AUDIO_RATE)
        block = b'\x00' * 4096 * 4
        while samples:
            count = min(4096, samples)
            output.writeframesraw(block[:count * 4])
            samples -= count


def join_audio(paths: list[Path], output: Path) -> None:
    with wave.open(str(output), 'wb') as writer:
        writer.setnchannels(2)
        writer.setsampwidth(2)
        writer.setframerate(AUDIO_RATE)
        for path in paths:
            with wave.open(str(path), 'rb') as reader:
                while chunk := reader.readframes(16384):
                    writer.writeframesraw(chunk)


def inspect_output(path: Path, width: int, height: int, fps: int, frames: int, audio: bool) -> dict:
    metadata = probe(path)
    video = next(s for s in metadata['streams'] if s['codec_type'] == 'video')
    actual_frames = int(video.get('nb_frames', 0))
    if (video['width'], video['height']) != (width, height) or actual_frames != frames:
        raise RuntimeError(f'Render verification failed: expected {width}x{height}/{frames} frames; got {video}')
    if video['codec_name'] != 'h264' or video.get('pix_fmt') != 'yuv420p':
        raise RuntimeError('Export is not compatible H.264/yuv420p')
    streams = [s for s in metadata['streams'] if s['codec_type'] == 'audio']
    if audio and (not streams or abs(float(streams[0]['duration']) - frames / fps) > 0.06):
        raise RuntimeError('Output audio duration does not match video')
    return {'width': width, 'height': height, 'fps': fps, 'frames': actual_frames,
            'video_duration': float(video['duration']), 'audio_duration': float(streams[0]['duration']) if streams else None,
            'video_codec': video['codec_name'], 'audio_codec': streams[0]['codec_name'] if streams else None}


def render(project: Path, plan_path: Path, cfg: dict, preview: bool = False) -> Path:
    film = read_json(project / 'analysis/film.json')
    original = validate_source(film)
    source = Path(film['proxy']) if preview else original
    shots = read_json(project / 'analysis/shots.json')['shots']
    lookup = {s['shot_id']: s for s in shots}
    plan = read_json(plan_path)
    validate_plan(plan, shots, cfg)
    audio_volume = float(plan.get('audio_volume', 1))
    if plan.get('source_fingerprint') != film['fingerprint']:
        raise ValueError('This plan belongs to a different source film')
    fps = int(cfg['export']['fps'])
    if fps <= 0 or AUDIO_RATE % fps:
        raise ValueError('Output fps must be an integer divisor of 48000 (e.g. 24, 25, 30, 60)')
    width = even(cfg['preview']['width'] if preview else cfg['export']['width'])
    height = even(width / aspect(plan['aspect']))
    options = cfg['preview'] if preview else cfg['export']
    if cfg['export']['codec'] not in ('h264', 'libx264'):
        raise ValueError('This renderer currently supports h264/libx264 exports')
    destination = project / ('previews' if preview else 'exports') / f'{plan_path.stem}.mp4'
    manifest = destination.with_suffix('.json')
    relevant = [lookup[e['shot_id']] for e in plan['shots']]
    key = signature({'renderer': 3, 'source': fingerprint(source), 'plan': plan, 'shots': relevant,
                     'export': cfg['export'], 'options': options, 'reframing': cfg['reframing'],
                     'music': fingerprint(Path(plan['music_path'])) if plan['audio'] == 'music' else None})
    if destination.exists() and manifest.exists():
        saved = read_json(manifest)
        if saved['cache_key'] == key and saved.get('output_fingerprint') == fingerprint(destination):
            LOG.info('[RENDER] Reusing %s', destination)
            return destination
    cache = project / 'render_cache'
    cache.mkdir(exist_ok=True)
    audio_needed = plan['audio'] in ('original', 'dialogue_reduced')
    codec = ['-c:v', 'libx264', '-preset', str(options['preset']), '-crf', str(options['crf']),
             '-threads', str(cfg['export']['threads']), '-pix_fmt', 'yuv420p', '-video_track_timescale', '90000']
    parts, audios, framing = [], [], []
    total_frames = 0
    for i, edit in enumerate(plan['shots'], 1):
        shot = lookup[edit['shot_id']]
        frames = max(1, round(edit['duration'] * fps))
        duration = frames / fps
        if edit['source_in'] + duration > shot['duration'] + 1e-6:
            raise ValueError(f'Shot {shot["shot_id"]}: frame rounding exceeds shot boundary; shorten duration')
        mode, points = crop_track(shot, edit, width / height, film['proxy_width'] / film['proxy_height'], cfg)
        filters = filter_graph(mode, points, width, height, fps)
        filters = filters.replace('[0:v]', f"[0:{0 if preview else film['video_stream_index']}]")
        segment_key = signature({'source': fingerprint(source), 'shot': shot['start'], 'edit': edit,
                                 'filters': filters, 'codec': codec, 'frames': frames, 'audio': plan['audio']})
        video = cache / f'{segment_key}.mp4'
        audio = cache / f'{segment_key}.wav'
        start = shot['start'] + edit['source_in']
        LOG.info('[RENDER] %s shot %d/%d (#%d, %s)', plan_path.stem, i, len(plan['shots']), shot['shot_id'], mode)
        if not video.exists():
            partial = video.with_suffix('.partial.mp4')
            run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{start:.6f}', '-i', str(source),
                 '-filter_complex_threads', str(cfg['export']['threads']), '-filter_complex', filters,
                 '-map', '[v]', '-an', '-frames:v', str(frames), *codec, str(partial)])
            check = next(s for s in probe(partial)['streams'] if s['codec_type'] == 'video')
            if int(check.get('nb_frames', 0)) != frames:
                raise RuntimeError(f'Source ended before requested shot {shot["shot_id"]}')
            partial.replace(video)
        if audio_needed and not audio.exists():
            partial_audio = audio.with_suffix('.partial.wav')
            if film['audio_streams']:
                audio_filter = f'aresample={AUDIO_RATE}:async=1:first_pts=0,apad,atrim=end_sample={frames * AUDIO_RATE // fps},asetpts=PTS-STARTPTS'
                if plan['audio'] == 'dialogue_reduced':
                    # Explicit approximation: center cancellation; not source separation.
                    audio_filter = 'aformat=channel_layouts=stereo,pan=stereo|c0=0.5*c0-0.5*c1|c1=0.5*c1-0.5*c0,' + audio_filter
                run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{start:.6f}', '-i', str(source),
                     '-map', '0:a:0', '-vn', '-af', audio_filter, '-t', f'{duration:.9f}',
                     '-ac', '2', '-ar', str(AUDIO_RATE), '-c:a', 'pcm_s16le', str(partial_audio)])
            else:
                silence(partial_audio, frames * AUDIO_RATE // fps)
            partial_audio.replace(audio)
        parts.append(video)
        if audio_needed:
            audios.append(audio)
        total_frames += frames
        framing.append({'shot_id': shot['shot_id'], 'mode': mode, 'track': points, 'frames': frames})
    # Fixed local filenames keep concat-demuxer quoting independent of arbitrary source paths.
    with tempfile.TemporaryDirectory(prefix='render-', dir=cache) as workspace:
        scratch = Path(workspace)
        card = plan.get('end_card', {})
        if card.get('enabled'):
            card_frames = max(1, round(card['duration'] * fps))
            picture, video = scratch / 'card.png', scratch / 'card.mp4'
            draw_card(picture, width, height, card)
            run(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-framerate', str(fps), '-i', str(picture),
                 '-an', '-frames:v', str(card_frames), *codec, str(video)])
            parts.append(video)
            total_frames += card_frames
            if audio_needed:
                audio = scratch / 'card.wav'
                silence(audio, card_frames * AUDIO_RATE // fps)
                audios.append(audio)
        for i, part in enumerate(parts):
            (scratch / f'part_{i:04d}.mp4').symlink_to(part.resolve())
        listing = scratch / 'concat.txt'
        listing.write_text(''.join(f"file 'part_{i:04d}.mp4'\n" for i in range(len(parts))), encoding='utf-8')
        joined = scratch / 'video.mp4'
        run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing), '-c:v', 'copy', '-an', str(joined)])
        partial = destination.with_suffix('.partial.mp4')
        command = ['ffmpeg', '-y', '-v', 'error', '-i', str(joined)]
        if audio_needed:
            joined_audio = scratch / 'audio.wav'
            join_audio(audios, joined_audio)
            command += ['-i', str(joined_audio), '-map', '0:v:0', '-map', '1:a:0',
                        '-af', f'volume={audio_volume:.4f}', '-c:a', 'aac', '-b:a', '192k']
        elif plan['audio'] == 'music':
            command += ['-stream_loop', '-1', '-i', str(Path(plan['music_path']).resolve()),
                        '-map', '0:v:0', '-map', '1:a:0', '-af', f'volume={audio_volume:.4f}',
                        '-c:a', 'aac', '-b:a', '192k', '-ar', str(AUDIO_RATE)]
        else:
            command += ['-map', '0:v:0', '-an']
        command += ['-c:v', 'copy', '-t', f'{total_frames / fps:.9f}', '-movflags', '+faststart', str(partial)]
        run(command)
        verification = inspect_output(partial, width, height, fps, total_frames, plan['audio'] != 'muted')
        partial.replace(destination)
    write_json(manifest, {'cache_key': key, 'output_fingerprint': fingerprint(destination),
                          'plan': str(plan_path), 'source': str(source), 'verification': verification, 'framing': framing})
    LOG.info('[DONE] %s (%.2fs)', destination, total_frames / fps)
    return destination
