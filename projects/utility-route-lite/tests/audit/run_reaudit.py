"""Independent re-audit runner; preserves historical evidence and app sources."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'docs/audits/evidence/gate-a-reaudit'
OUT.mkdir(parents=True,exist_ok=True)
APP=Path('/Applications/QGIS-final-4_2_3.app/Contents')
ENV=os.environ.copy()
ENV.update(PYTHONHOME=str(APP/'Resources'),PYTHONPATH=':'.join(map(str,[ROOT,APP/'Resources/python3.12',APP/'Resources/python3.12/lib-dynload',APP/'Resources/python3.12/site-packages',APP/'Resources/qgis/python/plugins'])),QGIS_PREFIX_PATH=str(APP/'Resources/qgis'),QT_PLUGIN_PATH=str(APP/'PlugIns'),QT_QPA_PLATFORM='offscreen',PROJ_DATA=str(APP/'Resources/qgis/proj'),GDAL_DATA=str(APP/'Resources/qgis/gdal'),PYTHONDONTWRITEBYTECODE='1')
PYTHON=str(APP/'MacOS/python3.12')
records=[]
def execute(name,args,env=None,cwd=ROOT):
    result=subprocess.run(args,cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (OUT/(name+'.txt')).write_text(result.stdout)
    records.append({'name':name,'argv':args,'cwd':str(cwd),'exit_code':result.returncode})
    print(name,'exit',result.returncode,flush=True)
    return result

def manifest():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'utility_route_lite').rglob('*')) if p.is_file() and '__pycache__' not in str(p)}

before=manifest()
(OUT/'application-before.json').write_text(json.dumps(before,indent=2))
historical=ROOT/'docs/audits/evidence/gate-a'
backup={p:p.read_bytes() for p in historical.iterdir() if p.is_file()}
try:
    if '--baseline-only' not in sys.argv:
        execute('environment',[PYTHON,'-c',"import os,sys,json,qgis.core; from qgis.PyQt.QtCore import QT_VERSION_STR; import utility_route_lite.core.builder as b; print(json.dumps({'python':sys.version,'executable':sys.executable,'qgis':qgis.core.Qgis.QGIS_VERSION,'qt':QT_VERSION_STR,'builder':b.__file__,'env':{k:os.environ.get(k) for k in ('PYTHONHOME','PYTHONPATH','QGIS_PREFIX_PATH','QT_PLUGIN_PATH','QT_QPA_PLATFORM','PROJ_DATA','GDAL_DATA','PYTHONDONTWRITEBYTECODE')}},indent=2))"],ENV)
        for name,file in [('existing-core','tests/test_builder_core.py'),('independent-core','tests/audit/test_graph_gate.py'),('new-core','tests/test_gate_a_regressions.py'),('existing-qgis','tests/qgis_builder.py'),('independent-qgis','tests/audit/qgis_graph_gate.py'),('new-qgis','tests/audit/qgis_remediation.py'),('crs-qgis','tests/test_crs_contract.py')]:
            execute(name,[PYTHON,str(ROOT/file),'-v'],ENV)
        execute('full-discovery-system',[sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py','-v'])
        execute('full-discovery-qgis',[PYTHON,'-m','unittest','discover','-s','tests','-p','test_*.py','-v'],ENV)
    # Reconstruct newly-added baseline files verbatim from saved diffs.
    with tempfile.TemporaryDirectory(prefix='url-original-') as temp:
        old=Path(temp)
        shutil.copytree(ROOT/'utility_route_lite',old/'utility_route_lite',ignore=shutil.ignore_patterns('__pycache__'))
        for directory in ('tests','examples','docs/contract'):
            shutil.copytree(ROOT/directory,old/directory,ignore=shutil.ignore_patterns('__pycache__'))
        (old/'docs/audits/evidence/gate-a').mkdir(parents=True)
        blocks=(ROOT/'docs/audits/evidence/prompt06-plugin.diff').read_text().split('diff -ruN ')[1:]
        restored=[]
        for block in blocks:
            lines=block.splitlines(keepends=True)
            if '1969-12-31' not in lines[1]: continue
            relative=lines[2].split('/current/')[1].split('\t')[0]
            data=''.join(line[1:] for line in lines[4:] if line.startswith('+'))
            path=old/relative; path.parent.mkdir(parents=True,exist_ok=True);path.write_text(data)
            restored.append(relative)
        for block in (ROOT/'docs/audits/evidence/prompt06-final-adjustments.diff').read_text().split('diff -ruN ')[1:]:
            lines=block.splitlines(keepends=True)
            relative=lines[2].split('/current/')[1].split('\t')[0]
            source=(old/relative).read_text().splitlines(keepends=True); output=[]; cursor=0;i=3
            while i<len(lines):
                match=re.match(r'@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@',lines[i])
                assert match,lines[i]
                start=int(match.group(1))-1;output.extend(source[cursor:start]);cursor=start;i+=1
                while i<len(lines) and not lines[i].startswith('@@'):
                    line=lines[i];i+=1
                    if line.startswith((' ','-')):
                        assert source[cursor]==line[1:],(relative,cursor)
                        cursor+=1
                    if line.startswith((' ','+')): output.append(line[1:])
            output.extend(source[cursor:]);(old/relative).write_text(''.join(output))
        expected=json.loads((historical/'application-before.json').read_text())
        verified={p:hashlib.sha256((old/p).read_bytes()).hexdigest()==expected[p] for p in restored}
        assert all(verified.values()),verified
        (OUT/'baseline-reconstruction.json').write_text(json.dumps(verified,indent=2))
        old_env=ENV.copy();old_env['PYTHONPATH']=str(old)+':'+ENV['PYTHONPATH']
        execute('original-independent-core',[PYTHON,str(old/'tests/audit/test_graph_gate.py'),'-v'],old_env,old)
        execute('original-independent-qgis',[PYTHON,str(old/'tests/audit/qgis_graph_gate.py'),'-v'],old_env,old)
        execute('original-new-regressions',[PYTHON,str(old/'tests/test_gate_a_regressions.py'),'-v'],old_env,old)
        execute('original-fixture-adapter',[PYTHON,'-m','unittest','discover','-s','tests','-p','test_graph_fixtures.py','-v'],old_env,old)
finally:
    for path,data in backup.items(): path.write_bytes(data)
    after=manifest(); (OUT/'application-after.json').write_text(json.dumps(after,indent=2))
    assert before==after,'application changed during audit'
    (OUT/('commands-baseline.json' if '--baseline-only' in sys.argv else 'commands.json')).write_text(json.dumps(records,indent=2))
