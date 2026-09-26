"""Creative decisions only. A future Astra adapter can emit this same editable EDL."""
from __future__ import annotations
import math
import random
from pathlib import Path
from .shot_ranker import add_visual_descriptors, eligible, score, similarity, tokens
from .thumbnails import contact_sheets
from .utils import LOG, aspect, read_json, signature, write_json

ROLES = ['intro', 'establish', 'build', 'accelerate', 'peak', 'release', 'end-image']


def database_signature(shots: list[dict]) -> str:
    return signature([{k: s[k] for k in ('shot_id', 'start', 'end')} for s in shots])


def validate_plan(plan: dict, shots: list[dict], cfg: dict) -> None:
    if plan.get('database_signature') != database_signature(shots):
        raise ValueError('Shot boundaries differ from this plan. Generate a new plan from the current analysis.')
    aspect(plan['aspect'])
    if plan['audio'] not in ('original', 'muted', 'music', 'dialogue_reduced'):
        raise ValueError('Unknown audio mode')
    volume = float(plan.get('audio_volume', 1))
    if not math.isfinite(volume) or not 0 <= volume <= 2:
        raise ValueError('Audio volume must be between 0 and 2')
    if plan['audio'] == 'music' and not Path(plan.get('music_path', '')).is_file():
        raise ValueError('Music mode needs an existing music_path')
    by_id = {s['shot_id']: s for s in shots}
    if not plan.get('shots'):
        raise ValueError('Reel plan must contain at least one shot')
    for item in plan['shots']:
        if item['shot_id'] not in by_id:
            raise ValueError(f"Unknown shot ID {item['shot_id']}")
        start, duration = float(item['source_in']), float(item['duration'])
        if not math.isfinite(start + duration) or start < 0 or duration < 1 / cfg['export']['fps']:
            raise ValueError('Shot offset must be nonnegative and duration at least one output frame')
        if start + duration > by_id[item['shot_id']]['duration'] + 0.0001:
            raise ValueError(f"Shot {item['shot_id']} extends beyond its source boundary")
        if item.get('crop_mode', 'auto') not in ('auto', 'smart_crop', 'fit', 'letterbox', 'blur_background'):
            raise ValueError('Unknown crop mode')
        if 'crop_center' in item and (len(item['crop_center']) != 2 or not all(0 <= v <= 1 for v in item['crop_center'])):
            raise ValueError('crop_center must contain normalized x,y coordinates in [0,1]')
    card = plan.get('end_card', {})
    if card.get('enabled') and (not math.isfinite(float(card['duration'])) or card['duration'] <= 0):
        raise ValueError('End-card duration must be positive')


def build_plan(shots: list[dict], film: dict, cfg: dict, request: dict, variant: int,
               prior_ids: set[int], reel_id: str) -> dict:
    mood = tokens(request['mood'])
    treatments = ['atmosphere', 'energy', 'emotion']
    treatment = treatments[variant % 3]
    rng = random.Random(request.get('seed', 42) + variant * 1009)
    card = dict(cfg['end_card'])
    fps = int(cfg['export']['fps'])
    target_frames = round(request['duration'] * fps)
    card_frames = round(card['duration'] * fps) if card['enabled'] else 0
    remaining = target_frames - card_frames
    if remaining < fps:
        raise ValueError('Duration must leave at least one second of footage after the end card')
    candidates = eligible(shots, film['duration'], request['spoilers'], cfg, request.get('excluded_ranges', []))
    if not candidates:
        raise ValueError('No eligible shots. Check spoiler settings and excluded ranges.')
    if sum(math.floor(s['duration'] * fps) for s in candidates) < remaining:
        raise ValueError('Not enough distinct eligible footage for this duration; shorten reel or relax exclusions.')
    tendency = [v for k, v in cfg['pacing'].items() if k in mood]
    average = sum(tendency) / len(tendency) if tendency else cfg['pacing']['default']
    average *= [1.0, 0.75, 1.2][variant % 3]
    count = max(3, min(40, round(remaining / fps / average)))
    selected, edits = [], []
    beat = 0
    while remaining > 0:
        phase = min(1, (target_frames - card_frames - remaining) / max(1, target_frames - card_frames))
        role = ROLES[min(6, int(phase * 7))]
        # Deliberate opening/closing holds, accelerated middle.
        length_factor = 1.3 if phase < 0.2 or phase > 0.8 else 0.65 if phase > 0.45 else 1.0
        wanted = min(remaining, max(1, round(average * length_factor * fps)))
        if remaining - wanted < average * fps * 0.6:
            wanted = remaining
        available = [s for s in candidates if s['shot_id'] not in {x['shot_id'] for x in selected}]
        if not available:
            raise ValueError('Ran out of distinct shots')
        def merit(s: dict) -> float:
            diversity = max((similarity(s, prev, cfg) for prev in selected), default=0)
            role_bonus = (0.25 * s['motion_score'] if role in ('accelerate', 'peak') else
                          0.2 * (1 - s['motion_score']) if role in ('release', 'end-image') else 0)
            return (score(s, mood, cfg, treatment) - cfg['ranking']['diversity'] * diversity
                    - (1.5 if s['shot_id'] in prior_ids else 0) + role_bonus
                    + 0.15 * min(1, s['duration'] * fps / wanted)
                    + (0.45 * (1 - s['face_fraction']) if role in ('establish', 'accelerate') else 0)
                    - (0.45 * s['face_fraction'] if selected and sum(p['face_fraction'] for p in selected) / len(selected) > 0.5 else 0)
                    + rng.uniform(0, 0.08))
        full_length = [s for s in available if math.floor(s['duration'] * fps) >= wanted]
        pool = full_length if full_length and (role in ('intro', 'release', 'end-image') or remaining == wanted) else available
        ranked = sorted(pool, key=merit, reverse=True)
        chosen = ranked[0]
        other_capacity = sum(math.floor(s['duration'] * fps) for s in available if s['shot_id'] != chosen['shot_id'])
        wanted = max(wanted, remaining - other_capacity)
        frames = min(wanted, math.floor(chosen['duration'] * fps + 1e-6))
        # Absorb a tiny tail, keeping frame-accurate total duration.
        if 0 < remaining - frames < fps // 2 and remaining <= math.floor(chosen['duration'] * fps):
            frames = remaining
        duration = frames / fps
        offset = max(0, (chosen['duration'] - duration) * (0.35 + rng.random() * 0.3))
        edits.append({'shot_id': chosen['shot_id'], 'source_in': round(offset, 6), 'duration': duration,
                      'role': role, 'crop_mode': cfg['reframing']['default_mode'], 'locked': False})
        selected.append(chosen)
        remaining -= frames
        beat += 1
    plan = {'schema_version': 1, 'reel_id': reel_id, 'target_duration': target_frames / fps,
            'database_signature': database_signature(shots),
            'source_fingerprint': film.get('fingerprint'),
            'aspect': request['aspect'], 'mood': request['mood'], 'spoilers': request['spoilers'],
            'audio': request['audio'], 'audio_volume': request.get('audio_volume', 1),
            'music_path': request.get('music_path'),
            'treatment': treatment, 'seed': request.get('seed', 42) + variant * 1009,
            'end_card': card, 'shots': edits,
            'notes': ['Spoiler controls are temporal/manual heuristics, not plot understanding.',
                      'Muted audio is the default dialogue-avoidance strategy.']}
    validate_plan(plan, shots, cfg)
    return plan


def generate(project: Path, cfg: dict, request: dict) -> list[Path]:
    film = read_json(project / 'analysis/film.json')
    db = project / 'analysis/shots.json'
    if not db.exists():
        raise ValueError('Run analyze before generating reels')
    shots = read_json(db)['shots']
    add_visual_descriptors(shots, project)
    exclusions = list(cfg['spoilers']['excluded_ranges'])
    manual = project / 'analysis/exclusions.json'
    if manual.exists():
        exclusions += read_json(manual).get('excluded_ranges', [])
    request = {**request, 'excluded_ranges': exclusions}
    ids = [int(p.stem[5:]) for p in (project / 'reel_plans').glob('reel_*.json') if p.stem[5:].isdigit()]
    start = max(ids, default=0) + 1
    paths, prior = [], set()
    for index in range(request['variants']):
        reel_id = f'reel_{start + index:03d}'
        plan = build_plan(shots, film, cfg, request, index, prior, reel_id)
        prior.update(s['shot_id'] for s in plan['shots'])
        path = project / 'reel_plans' / f'{reel_id}.json'
        write_json(path, plan)
        paths.append(path)
        ranked = sorted(eligible(shots, film['duration'], request['spoilers'], cfg, exclusions),
                        key=lambda s: score(s, tokens(request['mood']), cfg, plan['treatment']), reverse=True)
        contact_sheets(ranked[:48], project, f'{reel_id}_candidates')
        selected_ids = [s['shot_id'] for s in plan['shots']]
        lookup = {s['shot_id']: s for s in shots}
        contact_sheets([lookup[i] for i in selected_ids], project, f'{reel_id}_selected')
        LOG.info('[DIRECTOR] %s: %s, %d shots', reel_id, plan['treatment'], len(plan['shots']))
    return paths
