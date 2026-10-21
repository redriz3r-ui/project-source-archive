"""Analyze metadata only. Raw input is never serialized into output."""
import json
import math
import re
from collections import Counter
from datetime import datetime
from urllib.parse import urlsplit

from .privacy import endpoint, headers, number, MIMES, METHODS
from .http_analysis import inspect_headers
from .frontend import asset_kind
from .realtime import classify_realtime
from .streaming import streaming_protocols

def analyze(har, synthetic=False):
 if not isinstance(har,dict) or not isinstance(har.get('log'),dict) or not isinstance(har['log'].get('entries'),list):
  raise ValueError('Expected HAR log.entries array')
 entries=har['log']['entries']
 if len(entries)>100000: raise ValueError('Capture exceeds 100,000 entry limit')
 rows=[]; starts=[]; host_aliases={}
 for i,e in enumerate(entries):
  if not isinstance(e,dict) or not isinstance(e.get('request'),dict) or not isinstance(e.get('response'),dict): raise ValueError(f'Invalid entry {i+1}')
  req,res=e['request'],e['response']
  if not isinstance(req.get('url'),str): raise ValueError(f'Missing URL in entry {i+1}')
  host,path=endpoint(req['url'])
  try: raw_host=urlsplit(req['url']).hostname or '[unknown]'
  except ValueError: raw_host='[invalid]'
  if raw_host not in host_aliases: host_aliases[raw_host]=f'H{len(host_aliases)+1}'
  host=host_aliases[raw_host]+' / '+host
  rh=headers(res.get('headers',[]))
  rawmime=str(res.get('content',{}).get('mimeType','')).split(';')[0].lower() if isinstance(res.get('content',{}),dict) else ''
  mime=rawmime if rawmime in MIMES else 'other'
  rawpath=urlsplit(req['url']).path.lower()
  protocols=streaming_protocols(rawpath,mime)
  status=int(number(res.get('status')))
  realtime=classify_realtime(rawpath,mime,status,rh)
  kind='media' if protocols else 'realtime' if realtime else asset_kind(rawpath,mime)
  cacheflags,security=inspect_headers(rh)
  try: start=datetime.fromisoformat(e.get('startedDateTime','').replace('Z','+00:00')).timestamp()
  except (ValueError,TypeError,AttributeError): start=None
  starts.append(start)
  init=e.get('_initiator',{}); it=init.get('type') if isinstance(init,dict) else None
  method=req.get('method','GET')
  rows.append(dict(id=f'R{i+1}',host=host,endpoint=path,method=method if method in METHODS else 'OTHER',status=status,mime=mime,kind=kind,duration_ms=number(e.get('time')),size_bytes=number(res.get('bodySize')),initiator=it if it in {'parser','script','preload','other'} else 'unknown',cache=cacheflags,security_headers=security,realtime=realtime,protocols=sorted(set(protocols))))
 base=min((s for s in starts if s is not None),default=0)
 for row,start in zip(rows,starts): row['start_ms']=round(max(0,(start-base)*1000),2) if start is not None else None
 findings=[]
 def finding(label,classification,confidence,evidence,detail):
  findings.append(dict(id=f'F{len(findings)+1}',title=label,classification=classification,confidence=confidence,evidence=evidence,detail=detail))
 for kind,label in [('frontend','Frontend asset delivery'),('api','API-like traffic'),('realtime','Real-time transport indicators'),('media','Media transport indicators')]:
  ids=[r['id'] for r in rows if r['kind']==kind and not (kind=='realtime' and r['realtime']=='Polling candidate (inferred)') and not (kind=='media' and r['protocols']==['WebRTC indicator (inferred)'])]
  if ids: finding(label,'OBSERVED','high',ids,'Metadata matches documented classification rules. API-like does not establish an internal service boundary; polling and WebRTC labels are hypotheses.')
 for label,predicate in [('Polling candidate',lambda r:r['realtime']=='Polling candidate (inferred)'),('WebRTC candidate',lambda r:'WebRTC indicator (inferred)' in r['protocols'])]:
  ids=[r['id'] for r in rows if predicate(r)]
  if ids: finding(label,'INFERRED','low',ids,'URL or MIME hints alone do not establish repeated polling or an active WebRTC session.')
 if any(r['initiator']=='script' for r in rows): finding('Script-initiated loading','OBSERVED','high',[r['id'] for r in rows if r['initiator']=='script'],'HAR initiator metadata identifies script activity; it does not establish exact initialization dependencies.')
 finding('Component grouping','INFERRED','medium',[r['id'] for r in rows],'Graph groups requests by metadata role. Hostnames are privacy-normalized; per-capture aliases preserve distinct observed hosts. Browser edges represent requests, not backend-to-backend dependencies.')
 finding('Production backend and framework','UNKNOWN','unknown',[],'Server language, databases, deployment boundaries, frontend framework and WebRTC media sessions cannot be established from these metadata alone.')
 return dict(schema_version=1,synthetic=synthetic,warnings=['Imported HARs may contain credentials, private data and media bodies. Only redacted metadata is retained in reports.','Hosts use per-capture aliases to retain distinct host counts while masking subdomains. Custom domain labels can still identify an organization; review reports before sharing.'],requests=rows,findings=findings,summary=dict(total_requests=len(rows),unique_hosts=len({r['host'] for r in rows}),api_requests=sum(r['kind']=='api' for r in rows),websocket_handshakes=sum(r['realtime']=='WebSocket' for r in rows),protocols=sorted({p for r in rows for p in r['protocols']}),average_duration_ms=round(sum(r['duration_ms'] for r in rows)/len(rows),2) if rows else 0))
