from __future__ import annotations
import copy
from datetime import datetime, timezone
from pathlib import Path
import re
from .reel_director import validate_plan
from .shot_ranker import add_visual_descriptors, eligible, score, similarity, tokens
from .utils import read_json, write_json


def plan_path(project: Path, reel_id: str) -> Path:
    if not re.fullmatch(r'[A-Za-z0-9_-]+', reel_id):
        raise ValueError('Reel ID must use letters, numbers, underscore or hyphen')
    path = project / 'reel_plans' / f'{reel_id}.json'
    if not path.exists():
        raise ValueError(f'Unknown reel {reel_id}')
    return path


def edit_plan(project: Path, reel_id: str, action: str, cfg: dict, **args) -> Path:
    path = plan_path(project, reel_id)
    plan = read_json(path)
    before = copy.deepcopy(plan)
    shots = read_json(project / 'analysis/shots.json')['shots']
    add_visual_descriptors(shots, project)
    lookup = {s['shot_id']: s for s in shots}
    if action == 'reorder':
        order = args['order']
        if sorted(order) != list(range(1, len(plan['shots']) + 1)):
            raise ValueError('Order must list every 1-based position exactly once')
        plan['shots'] = [plan['shots'][i - 1] for i in order]
    elif action == 'regenerate':
        film = read_json(project / 'analysis/film.json')
        exclusions = list(cfg['spoilers']['excluded_ranges'])
        if (project / 'analysis/exclusions.json').exists():
            exclusions += read_json(project / 'analysis/exclusions.json')['excluded_ranges']
        allowed = eligible(shots, film['duration'], plan['spoilers'], cfg, exclusions)
        used = {item['shot_id'] for item in plan['shots'] if item.get('locked')}
        old = {item['shot_id'] for item in plan['shots']}
        selected = [lookup[i] for i in used]
        for item in plan['shots']:
            if item.get('locked'):
                continue
            candidates = [s for s in allowed if s['shot_id'] not in used and s['duration'] >= item['duration']]
            if not candidates:
                raise ValueError('Not enough eligible replacement shots; plan left unchanged')
            chosen = max(candidates, key=lambda s: score(s, tokens(plan['mood']), cfg, plan.get('treatment', 'atmosphere'))
                         - (1.5 if s['shot_id'] in old else 0)
                         - cfg['ranking']['diversity'] * max((similarity(s, p, cfg) for p in selected), default=0))
            item.update(shot_id=chosen['shot_id'], source_in=max(0, (chosen['duration'] - item['duration']) / 2))
            item.pop('crop_center', None)
            used.add(chosen['shot_id'])
            selected.append(chosen)
    else:
        position = args['position']
        if not 1 <= position <= len(plan['shots']):
            raise ValueError(f'Position must be 1..{len(plan["shots"])}')
        item = plan['shots'][position - 1]
        if action == 'replace':
            if args['shot_id'] not in lookup:
                raise ValueError('Replacement shot does not exist')
            item.update(shot_id=args['shot_id'], source_in=0.0)
            item.pop('crop_center', None)
        elif action == 'remove':
            plan['shots'].pop(position - 1)
        elif action == 'duration':
            item['duration'] = args['duration']
        elif action == 'crop':
            item['crop_mode'] = args['mode']
            if args.get('center') is not None:
                item['crop_center'] = args['center']
        elif action == 'lock':
            item['locked'] = not args.get('unlock', False)
    validate_plan(plan, shots, cfg)
    plan['target_duration'] = sum(s['duration'] for s in plan['shots']) + (plan['end_card']['duration'] if plan['end_card']['enabled'] else 0)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    write_json(path.parent / 'history' / f'{reel_id}_{stamp}.json', before)
    write_json(path, plan)
    return path
