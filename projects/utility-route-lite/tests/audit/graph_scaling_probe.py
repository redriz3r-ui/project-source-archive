"""Bounded synthetic scaling evidence; no asserted performance promise."""
import copy
import json
from pathlib import Path
import resource
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_graph_gate import case, build
rows = []
for n in (1000, 2000, 4000):
    c = case(); template = c['source']['features'][0]
    c['source']['features'] = []
    for i in range(n):
        f = copy.deepcopy(template)
        f['properties']['asset_key'] = f'e{i:06d}'
        f['geometry']['coordinates'] = [[i,0],[i+1,0]]
        c['source']['features'].append(f)
    start = time.perf_counter(); graph = build(c)
    assert len(graph['edges']) == n
    assert graph['build_summary']['component_count'] == 1
    rows.append({'edges':n, 'elapsed_seconds':time.perf_counter()-start,
                 'process_lifetime_peak_rss_bytes_macos':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
print(json.dumps(rows,indent=2))
