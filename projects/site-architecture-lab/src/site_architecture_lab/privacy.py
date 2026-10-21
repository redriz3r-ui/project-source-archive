"""Conservative allowlist normalization; no input bodies or secrets leave this layer."""
import math
import re
from urllib.parse import urlsplit

SAFE_SEGMENTS = set('api v1 v2 v3 static assets js css images img fonts media video stream streams hls dash manifest playlist index master live socket ws websocket events poll polling init config bootstrap public homepage health status rooms list search app main vendor chunk runtime graphql webrtc stun turn'.split())
EXTENSIONS = {'js','css','png','jpg','jpeg','gif','svg','webp','woff','woff2','ico','m3u8','mpd','ts','m4s','mp4','html','json','map'}
METHODS = {'GET','POST','PUT','PATCH','DELETE','OPTIONS','HEAD','CONNECT'}
MIMES = {'application/json','application/javascript','text/javascript','text/css','text/html','image/png','image/jpeg','image/svg+xml','text/event-stream','application/vnd.apple.mpegurl','application/x-mpegurl','application/dash+xml','video/mp2t','video/mp4','audio/mp4','application/octet-stream','font/woff2','application/sdp'}

def number(v):
 return max(0,float(v)) if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) else 0

def endpoint(url):
 """Keep only a vocabulary of structural segments; discard ALL other values."""
 try: u=urlsplit(url)
 except ValueError: return 'invalid-host','/[redacted]'
 host=(u.hostname or '').lower()
 # Numeric, local and arbitrary subdomains may carry identifiers. Keep registrable-looking
 # final labels only, masking all subdomains. No DNS or public-suffix lookup is performed.
 labels=host.split('.')
 if len(labels)<2 or any(re.search(r'[^a-z-]',x) for x in labels[-2:]) or len(labels[-2])>30:
  host='[redacted-host]'
 else: host=('.'.join(labels[-2:]) if len(labels)==2 else '[subdomain].'+'.'.join(labels[-2:]))
 parts=[]
 for part in u.path.split('/'):
  if not part: continue
  low=part.lower()
  if low in SAFE_SEGMENTS: parts.append(low)
  else:
   ext=low.rsplit('.',1)[-1] if '.' in low else ''
   parts.append('[asset].'+ext if ext in EXTENSIONS else '[redacted]')
 return host,'/'+ '/'.join(parts)

def headers(items):
 return {str(x.get('name','')).lower():str(x.get('value','')) for x in items if isinstance(x,dict)} if isinstance(items,list) else {}

