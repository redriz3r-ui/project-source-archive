from __future__ import annotations
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from fractions import Fraction
from typing import Any
import yaml

LOG = logging.getLogger('reel')
ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name, suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write('\n')
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def signature(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def fingerprint(path: Path) -> dict:
    stat = path.stat()
    return {'path': str(path.resolve()), 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}


def run(args: list[str]) -> subprocess.CompletedProcess:
    LOG.debug('Running %s', args)
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed ({result.returncode}):\n{result.stderr[-6000:]}')
    return result


def require_media_tools() -> None:
    for executable in ('ffmpeg', 'ffprobe'):
        if not shutil.which(executable):
            raise RuntimeError(f'{executable} is missing. Install FFmpeg and add it to PATH.')


def probe(path: Path) -> dict:
    return json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)]).stdout)


def rate(value: str) -> float:
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return 0.0


def config(path: Path | None = None) -> dict:
    with (path or ROOT / 'config.yaml').open(encoding='utf-8') as handle:
        cfg = yaml.safe_load(handle)
    # Fail early instead of allowing division by zero or unbounded allocations.
    for section, key in [('analysis', 'proxy_width'), ('analysis', 'proxy_fps'),
                         ('analysis', 'sample_fps'), ('analysis', 'max_samples_per_shot'),
                         ('analysis', 'workers'), ('export', 'fps'), ('export', 'width'),
                         ('export', 'height'), ('preview', 'width')]:
        if not math.isfinite(float(cfg[section][key])) or cfg[section][key] <= 0:
            raise ValueError(f'{section}.{key} must be positive')
    if not 0 <= cfg['reframing']['smoothing'] < 1:
        raise ValueError('reframing.smoothing must be in [0, 1)')
    if not 0 < float(cfg['analysis'].get('continuous_segment_seconds', 12)) <= 600:
        raise ValueError('analysis.continuous_segment_seconds must be in (0, 600]')
    return cfg


def active_project(root: Path, name: str | None) -> Path:
    if name:
        path = root / name
        if path.resolve().parent != root.resolve():
            raise ValueError('Project must be a directory name, not a path')
    else:
        marker = root / '.active.json'
        if not marker.exists():
            raise ValueError('No active project. Run ingest first, or use --project NAME.')
        path = root / read_json(marker)['project']
    if not (path / 'analysis/film.json').exists():
        raise ValueError(f'Project not found: {path}')
    return path


def validate_source(film: dict) -> Path:
    path = Path(film['source'])
    if not path.is_file() or fingerprint(path) != film['fingerprint']:
        raise ValueError('Source is missing or has changed. Restore it or ingest the new file.')
    return path


def even(value: float) -> int:
    return max(2, int(round(value / 2)) * 2)


def aspect(value: str) -> float:
    try:
        a, b = map(float, value.split(':'))
        if a <= 0 or b <= 0 or not math.isfinite(a / b):
            raise ValueError()
        return a / b
    except (ValueError, ZeroDivisionError):
        raise ValueError('Aspect must be positive WIDTH:HEIGHT, for example 9:16') from None
