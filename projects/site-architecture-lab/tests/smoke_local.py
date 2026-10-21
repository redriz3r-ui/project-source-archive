"""Explicit local integration check. Start ./run.sh before executing this file."""
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE='http://127.0.0.1:8765'
fixture=(Path(__file__).resolve().parents[1]/'examples/synthetic.har').read_bytes()
def request(path,body=None,headers=None):
 req=Request(BASE+path,data=body,headers=headers or {})
 try:
  with urlopen(req,timeout=10) as response: return response.status,response.read(),response.headers
 except HTTPError as error:return error.code,error.read(),error.headers

status,body,headers=request('/')
assert status==200 and b'<div id="root">' in body
assert "frame-ancestors 'none'" in headers['Content-Security-Policy']
print('PASS: dashboard served with security headers')
status,body,_=request('/api/report'); original=json.loads(body)
assert status==200 and original['summary']['total_requests']==14
print('PASS: analysis API returns synthetic metadata')
status,body,_=request('/api/import',b'{"log":null}',{'Content-Type':'application/json'})
assert status==400
assert json.loads(request('/api/report')[1])==original
print('PASS: malformed import rejected and previous analysis preserved')
status,_,_=request('/api/import',fixture,{'Content-Type':'application/json','Origin':'https://untrusted.example'})
assert status==403
print('PASS: cross-origin import blocked')
status,body,_=request('/api/import',fixture,{'Content-Type':'application/json'})
assert status==200 and json.loads(body)['summary']['unique_hosts']==5
assert b'EXAMPLE_SECRET' not in body
for name in ['architecture.md','architecture.mmd','requests-summary.json','technology-evidence.md','research-gaps.md']:
 status,body,_=request('/reports/'+name)
 assert status==200 and b'EXAMPLE_SECRET' not in body
print('PASS: valid import redacted and all five reports downloadable')
