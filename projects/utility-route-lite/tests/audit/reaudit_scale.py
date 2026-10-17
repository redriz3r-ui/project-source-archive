"""50k source/edge identity, shape, digest, reorder and cancellation audit."""
import gc
import hashlib
import json
from pathlib import Path
import resource
import sys
import time
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.regenerate_fixtures import benchmark
from utility_route_lite.core.builder import build_graph,BuildError
from utility_route_lite.core.serialization import digest
from qgis.core import Qgis
c=benchmark(50000)
kwargs=dict(source_crs_wkt=c['source_crs'],network_crs_wkt=c['network_crs'],layer_key=c['source_layer_key'],feature_key_field='asset_key',profile=c['rule_profile'])
records=[];signatures=[]
for order in ('forward','reverse'):
    start=time.perf_counter();g=build_graph(c['source']['features'],**kwargs);elapsed=time.perf_counter()-start
    assert len(c['source']['features'])==len(g['source_parts'])==len(g['edges'])==50000
    assert len(g['nodes'])==50001 and g['build_summary']['component_count']==1
    assert not g['transitions']
    edge_ids=set();node_ids={n['node_id'] for n in g['nodes']}
    for e in g['edges']:
        i=int(e['source_feature_key'].split('_')[1])
        assert e['vertices_xy']==[[i,0],[i+1,0]] and e['length_m']==1.0
        assert e['source_part_index']==0 and e['edge_status']=='OPEN' and e['direction']=='BOTH'
        # Independent SHA calculation for this float-free edge identity payload.
        payload=['edge',1,c['source_layer_key'],e['source_feature_key'],0,'START','END']
        expected='e_'+hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        assert e['edge_id']==expected and e['edge_id'] not in edge_ids;edge_ids.add(e['edge_id'])
        assert e['from_node_id'] in node_ids and e['to_node_id'] in node_ids
    for n in g['nodes']:
        payload=['node',1,c['network_crs'],'GEOMETRIC_ENDPOINT_ONLY',[float(v).hex() for v in n['xy']]]
        assert n['node_id']=='n_'+hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    signature={'graph_digest':g['graph_digest'],'source_snapshot_sha256':g['source_snapshot_sha256'],'profile_hash':g['profile_hash'],'edges_hash':digest(sorted(edge_ids)),'nodes_hash':digest(sorted(node_ids))}
    signatures.append(signature)
    records.append({'order':order,'input_edges':50000,'output_edges':len(g['edges']),'nodes':len(g['nodes']),'components':1,'build_seconds':elapsed,'peak_rss_bytes_macos':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,**signature})
    del g;gc.collect();c['source']['features'].reverse()
assert signatures[0]==signatures[1]
class Feedback:
    canceled=False
    def isCanceled(self):return self.canceled
feedback=Feedback();consumed=0
def source():
    global consumed
    for f in c['source']['features']:
        consumed+=1
        if consumed==500:feedback.canceled=True
        yield f
try:
    build_graph(source(),feedback=feedback,**kwargs)
    raise AssertionError('canceled build returned a graph')
except BuildError as e: assert e.code=='CANCELED'
assert consumed==500
print(json.dumps({'python':sys.version,'qgis':Qgis.QGIS_VERSION,'runs':records,'repeat_identity_and_fingerprints_equal':True,'cancellation_consumed':consumed,'cancellation_code':'CANCELED'},indent=2))
