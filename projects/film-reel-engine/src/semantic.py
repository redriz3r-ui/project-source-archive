"""Optional local Python provider: describe(image_path: str) -> JSON-compatible dict.

Configured providers are trusted code. No network or model is enabled by default.
External providers must implement their own credentials/consent policies.
"""
from __future__ import annotations
import hashlib
import importlib
from pathlib import Path
from .utils import read_json, signature, write_json


def describe(image: Path, cache: Path, settings: dict) -> dict:
    provider = settings.get('plugin')
    if not provider:
        return {}
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    key = signature({'frame': digest, 'provider': provider, 'version': settings['version']})
    target = cache / f'{key}.json'
    if target.exists():
        return read_json(target)
    result = importlib.import_module(provider).describe(str(image))
    if not isinstance(result, dict):
        raise ValueError('Semantic provider must return a dictionary')
    for field in ('semantic_tags', 'mood_tags'):
        if field in result and (not isinstance(result[field], list) or not all(isinstance(x, str) for x in result[field])):
            raise ValueError(f'Semantic {field} must be a list of strings')
    allowed = {key: result[key] for key in ('description', 'semantic_tags', 'mood_tags', 'spoiler_score') if key in result}
    write_json(target, allowed)
    return allowed
