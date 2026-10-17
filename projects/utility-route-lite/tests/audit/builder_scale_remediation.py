"""Measured synthetic Builder scaling without writing large fixture artifacts."""
import json
import resource
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.regenerate_fixtures import benchmark
from utility_route_lite.core.builder import build_graph

size = int(sys.argv[1])
case = benchmark(size)
started = time.perf_counter()
graph = build_graph(case['source']['features'], source_crs_wkt=case['source_crs'],
    network_crs_wkt=case['network_crs'], layer_key=case['source_layer_key'],
    feature_key_field='asset_key', profile=case['rule_profile'])
elapsed = time.perf_counter() - started
assert len(graph['edges']) == size
assert graph['build_summary']['component_count'] == 1
assert sum(e['length_m'] for e in graph['edges']) == size
print(json.dumps({'edges':size,'elapsed_seconds':elapsed,
    'peak_rss_bytes_macos':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    'component_count':graph['build_summary']['component_count'],
    'edge_count':len(graph['edges'])}, sort_keys=True))
