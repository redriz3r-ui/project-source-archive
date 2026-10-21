import json
from pathlib import Path

def generate(data, directory):
 out=Path(directory); out.mkdir(parents=True,exist_ok=True)
 rows=data['requests']
 banner='SYNTHETIC EXAMPLE — no observations of Chaturbate production.\n\n' if data['synthetic'] else 'Offline capture metadata analysis; findings apply only to this capture.\n\n'
 text='# Observable architecture\n\n'+banner
 for f in data['findings']:
  text+=f"## {f['classification']}: {f['title']}\n\nConfidence: {f['confidence']}. Evidence: {', '.join(f['evidence']) or 'none'}.\n\n{f['detail']}\n\n"
 text+='## Evidence inventory\n\n| ID | Host (normalized) | Endpoint | Type | Status |\n|---|---|---|---|---|\n'
 text+=''.join(f"| {r['id']} | {r['host']} | {r['endpoint']} | {r['kind']} | {r['status']} |\n" for r in rows)
 diagram='flowchart LR\n  browser["Browser (inferred capture origin)"]\n'
 for i,kind in enumerate(sorted({r['kind'] for r in rows})):
  diagram+=f'  browser --> n{i}["{kind}: observed requests; inferred group"]\n'
 (out/'architecture.md').write_text(text)
 (out/'architecture.mmd').write_text(diagram)
 (out/'requests-summary.json').write_text(json.dumps(data,indent=2,allow_nan=False))
 (out/'technology-evidence.md').write_text('# Technology evidence\n\n'+banner+'\n'.join(f"- {r['id']}: {r['mime']}; protocols: {', '.join(r['protocols']) or 'none'}; initiator: {r['initiator']}; caching: {', '.join(r['cache']) or 'not observed'}; security header names: {', '.join(r['security_headers']) or 'not observed'}." for r in rows)+'\n\nUNKNOWN: framework, origin backend, databases and CDN vendor. Asset names alone are insufficient framework evidence.\n')
 (out/'research-gaps.md').write_text("""# Research gaps

- HAR usually omits WebSocket frames, WebRTC sessions, JavaScript execution order, service-worker internals, and server-to-server traffic.
- Missing requests do not prove a protocol or technology is absent. Cached resources may be omitted or have zero/unknown sizes.
- Size uses HAR bodySize, with unavailable (-1) represented as zero; timings are HAR total durations. Missing start times remain unknown.
- Host normalization masks subdomains; per-capture aliases preserve distinct host counts. Public suffix boundaries are not inferred.
- Parser/script/preload initiators support loading observations but do not prove causal dependency chains. Raw initiator URLs/stacks are discarded.
- Polling requires repeated intervals to confirm; path matches are candidates only. SDP and URL hints do not prove an active WebRTC session.
- Next: inspect an authorized public homepage capture, compare loading order and cache headers, and manually inspect public script source if framework identification is needed.
- Never infer Django, Python, databases or internal service topology from historical claims.
""")
