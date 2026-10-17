"""Record focused Gate A round 2 checks without overwriting historical audit data."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/audits/evidence/gate-a-round2';OUT.mkdir(parents=True,exist_ok=True)
HISTORY=ROOT/'docs/audits/evidence/gate-a'
backup={p:p.read_bytes() for p in HISTORY.iterdir() if p.is_file()}
records=[]
def run(name,command):
    completed=subprocess.run(command,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (OUT/(name+'.txt')).write_text(completed.stdout)
    counts=re.search(r'Ran (\d+) tests?',completed.stdout)
    records.append({'name':name,'command':command,'exit_code':completed.returncode,'tests':int(counts[1]) if counts else None})
    print(name,'exit',completed.returncode,flush=True)
try:
    files=[('existing-core','tests/test_builder_core.py'),('original-independent-core','tests/audit/test_graph_gate.py'),('round1-core','tests/test_gate_a_regressions.py'),('existing-qgis','tests/qgis_builder.py'),('original-independent-qgis','tests/audit/qgis_graph_gate.py'),('round1-qgis','tests/audit/qgis_remediation.py'),('crs-qgis','tests/test_crs_contract.py'),('reaudit-core','tests/audit/test_reaudit_adversarial.py'),('reaudit-qgis','tests/audit/qgis_reaudit_adversarial.py'),('round2-core','tests/test_round2.py'),('round2-qgis','tests/audit/qgis_round2.py'),('scale-50k','tests/audit/reaudit_scale.py')]
    for name,file in files:
        run(name,['bash','scripts/run_qgis_scaffold_macos.sh','/Applications/QGIS-final-4_2_3.app',file])
    run('contract',[sys.executable,'scripts/check_contract.py'])
    for pattern in ['test_builder_core.py','test_gate_a_regressions.py','test_round2.py','test_contract.py','test_scaffold.py']:
        run('system-'+pattern[:-3],[sys.executable,'-m','unittest','discover','-s','tests','-p',pattern,'-v'])
    run('full-discovery-system',[sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py','-v'])
finally:
    for p,data in backup.items():p.write_bytes(data)
    (OUT/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
    snapshot={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'utility_route_lite').rglob('*')) if p.is_file() and '__pycache__' not in str(p)}
    (OUT/'application.json').write_text(json.dumps(snapshot,indent=2)+'\n')
