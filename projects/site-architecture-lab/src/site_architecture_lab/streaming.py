"""Passive media indicators only: never retrieve manifests or media."""
import re

def streaming_protocols(path,mime):
 protocols=[]
 for ext,protocol in [('.m3u8','HLS'),('.mpd','MPEG-DASH'),('.ts','Transport segment'),('.m4s','Fragmented media')]:
  if path.endswith(ext): protocols.append(protocol)
 if mime in {'application/vnd.apple.mpegurl','application/x-mpegurl'}: protocols.append('HLS')
 if mime=='application/dash+xml': protocols.append('MPEG-DASH')
 if mime in {'video/mp2t','video/mp4','audio/mp4'}: protocols.append('Media')
 if mime=='application/sdp' or re.search(r'/(webrtc|stun|turn)(/|$)',path): protocols.append('WebRTC indicator (inferred)')
 return protocols
