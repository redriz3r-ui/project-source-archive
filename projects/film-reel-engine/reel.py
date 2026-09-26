#!/usr/bin/env python3
"""Local-first film reel engine. Run python reel.py --help."""
from __future__ import annotations
import argparse
import logging
import math
from pathlib import Path
import sys
from src.editor import edit_plan, plan_path
from src.ingest import ingest
from src.reel_director import generate
from src.renderer import render
from src.shot_analysis import analyze
from src.utils import ROOT, active_project, aspect, config, read_json, require_media_tools


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--config', type=Path, default=ROOT / 'config.yaml')
    cli.add_argument('--projects-dir', type=Path, default=ROOT / 'projects')
    cli.add_argument('--project', help='Project directory name; defaults to last ingested film')
    cli.add_argument('--verbose', action='store_true')
    commands = cli.add_subparsers(dest='command', required=True)
    item = commands.add_parser('ingest', help='Inspect source and cache a lightweight proxy')
    item.add_argument('movie', type=Path)
    item = commands.add_parser('analyze', help='Detect shots and cache visual analysis')
    item.add_argument('--workers', type=int, help='Override configured worker count (1–4)')
    item = commands.add_parser('generate', help='Plan and render new reels from cached analysis')
    item.add_argument('--mood', default='atmospheric')
    item.add_argument('--duration', type=float, default=22)
    item.add_argument('--aspect', default='9:16')
    item.add_argument('--spoilers', choices=['low', 'medium', 'unrestricted'], default='low')
    item.add_argument('--variants', type=int, default=1)
    item.add_argument('--seed', type=int, default=42)
    item.add_argument('--audio', choices=['original', 'muted', 'music', 'dialogue_reduced'], default='muted')
    item.add_argument('--audio-volume', type=float, default=1.0, help='Audio gain from 0 to 2 (1 is unchanged)')
    item.add_argument('--music', type=Path)
    item.add_argument('--dialogue', choices=['avoid', 'allow'], default='avoid')
    item.add_argument('--preset', type=Path, help='JSON request preset, overridden by explicitly passed options')
    item.add_argument('--plan-only', action='store_true', help='Save EDLs and contact sheets without rendering')
    for name in ('preview', 'render'):
        item = commands.add_parser(name)
        item.add_argument('reel_id')
    item = commands.add_parser('status')
    for name in ('replace-shot', 'remove-shot', 'set-duration', 'set-crop', 'lock-shot'):
        item = commands.add_parser(name)
        item.add_argument('reel_id')
        item.add_argument('position', type=int, help='1-based position in the reel')
        if name == 'replace-shot':
            item.add_argument('shot_id', type=int)
        elif name == 'set-duration':
            item.add_argument('duration', type=float)
        elif name == 'set-crop':
            item.add_argument('mode', choices=['auto', 'smart_crop', 'fit', 'letterbox', 'blur_background'])
            item.add_argument('--center', type=float, nargs=2, metavar=('X', 'Y'))
        elif name == 'lock-shot':
            item.add_argument('--unlock', action='store_true')
    item = commands.add_parser('reorder')
    item.add_argument('reel_id')
    item.add_argument('order', nargs='+', type=int)
    item = commands.add_parser('regenerate', help='Replace unlocked selections without reanalysis or rendering')
    item.add_argument('reel_id')
    return cli


def main(argv: list[str] | None = None) -> int:
    arguments = argv if argv is not None else sys.argv[1:]
    args = parser().parse_args(arguments)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format='%(message)s')
    try:
        cfg = config(args.config)
        root = args.projects_dir.expanduser().resolve()
        if args.command in ('ingest', 'analyze', 'generate', 'render', 'preview'):
            require_media_tools()
        if args.command == 'ingest':
            ingest(args.movie, root, cfg)
            return 0
        project = active_project(root, args.project)
        if args.command == 'analyze':
            if args.workers is not None:
                if not 1 <= args.workers <= 4:
                    raise ValueError('Workers must be 1–4')
                cfg['analysis']['workers'] = args.workers
            analyze(project, cfg)
        elif args.command == 'generate':
            request = vars(args).copy()
            if args.preset:
                preset = read_json(args.preset)
                for key, value in preset.items():
                    option = '--' + key.replace('_', '-')
                    if not any(a == option or a.startswith(option + '=') for a in arguments):
                        request[key] = value
            if not math.isfinite(request['duration']) or not 1 <= request['duration'] <= 600:
                raise ValueError('Duration must be between 1 and 600 seconds')
            if not isinstance(request['variants'], int) or not 1 <= request['variants'] <= 20:
                raise ValueError('Variants must be between 1 and 20')
            if not math.isfinite(request['audio_volume']) or not 0 <= request['audio_volume'] <= 2:
                raise ValueError('Audio volume must be between 0 and 2')
            aspect(request['aspect'])
            request['music_path'] = str(args.music.expanduser().resolve()) if args.music else request.get('music_path')
            if request['audio'] == 'original' and request['dialogue'] == 'avoid':
                logging.info('[AUDIO] Original audio can contain dialogue; --dialogue avoid does not isolate speech. Using requested original audio.')
            if request['audio'] == 'dialogue_reduced':
                logging.info('[AUDIO] Experimental stereo center cancellation; may also remove music and does not guarantee speech removal.')
            paths = generate(project, cfg, request)
            if not args.plan_only:
                for path in paths:
                    render(project, path, cfg)
        elif args.command in ('preview', 'render'):
            render(project, plan_path(project, args.reel_id), cfg, preview=args.command == 'preview')
        elif args.command == 'status':
            film = read_json(project / 'analysis/film.json')
            print(f"Project: {project}\nSource: {film['source']}\nDuration: {film['duration'] / 60:.1f} minutes")
            database = project / 'analysis/shots.json'
            print(f"Indexed shots: {len(read_json(database)['shots']) if database.exists() else 'not analyzed'}")
            print('Plans: ' + ', '.join(p.stem for p in sorted((project / 'reel_plans').glob('*.json'))))
        else:
            action = {'replace-shot': 'replace', 'remove-shot': 'remove', 'set-duration': 'duration',
                      'set-crop': 'crop', 'lock-shot': 'lock'}.get(args.command, args.command)
            options = {k: v for k, v in vars(args).items() if k not in ('reel_id', 'command', 'config', 'project')}
            path = edit_plan(project, args.reel_id, action, cfg, **options)
            logging.info('[EDITOR] Saved %s. Run preview or render to review.', path)
        return 0
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
        logging.error('[ERROR] %s', exc)
        if args.verbose:
            logging.exception('Details')
        return 1
    except KeyboardInterrupt:
        logging.error('[INTERRUPTED] Completed shot checkpoints are retained. Rerun the command to resume.')
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
