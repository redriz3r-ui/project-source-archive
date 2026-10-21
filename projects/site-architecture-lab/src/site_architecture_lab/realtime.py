"""HAR handshake observations and explicitly tentative polling hints."""
import re

def classify_realtime(path,mime,status,response_headers):
 if status==101 and response_headers.get('upgrade','').lower()=='websocket': return 'WebSocket'
 if mime=='text/event-stream': return 'SSE'
 if re.search(r'/(poll|polling)(/|$)',path): return 'Polling candidate (inferred)'
 return None
