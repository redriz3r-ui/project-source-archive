import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .analysis import analyze
from .reports import generate

ROOT=Path(__file__).resolve().parents[2]
LIMIT=25*1024*1024

def load(path):
 if Path(path).stat().st_size>LIMIT: raise ValueError('HAR exceeds 25 MiB limit')
 return json.loads(Path(path).read_text())

def serve(port):
 state=analyze(load(ROOT/'examples/synthetic.har'),True)
 generate(state,ROOT/'reports')
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args): pass # do not log capture paths or request contents
  def reply(self,status,body,mime='application/json'):
   self.send_response(status); self.send_header('Content-Type',mime); self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'"); self.end_headers(); self.wfile.write(body)
  def allowed(self):
   return self.headers.get('Host') in {f'127.0.0.1:{port}',f'localhost:{port}'} and self.headers.get('Origin') in {None,f'http://127.0.0.1:{port}',f'http://localhost:{port}'}
  def do_GET(self):
   if not self.allowed(): return self.reply(403,b'{}')
   path=urlsplit(self.path).path
   if path=='/api/report': return self.reply(200,json.dumps(state,allow_nan=False).encode())
   if path.startswith('/reports/'):
    name=path.split('/')[-1]
    if name not in {'architecture.md','architecture.mmd','requests-summary.json','technology-evidence.md','research-gaps.md'}: return self.reply(404,b'{}')
    return self.reply(200,(ROOT/'reports'/name).read_bytes(),'text/plain; charset=utf-8')
   dist=ROOT/'dashboard/dist'; target=(dist/path.lstrip('/')).resolve()
   if not target.is_relative_to(dist.resolve()): return self.reply(404,b'{}')
   if not target.is_file(): target=dist/'index.html'
   if not target.exists(): return self.reply(503,b'Build dashboard first: npm --prefix dashboard run build','text/plain')
   return self.reply(200,target.read_bytes(),mimetypes.guess_type(target)[0] or 'application/octet-stream')
  def do_POST(self):
   nonlocal state
   if not self.allowed() or self.headers.get('Content-Type')!='application/json': return self.reply(403,b'{"error":"Same-origin JSON required"}')
   if self.path!='/api/import': return self.reply(404,b'{}')
   try:
    length=int(self.headers.get('Content-Length','0'))
    if not 0<length<=LIMIT: return self.reply(413,b'{"error":"Capture must be under 25 MiB"}')
    raw=json.loads(self.rfile.read(length)); candidate=analyze(raw)
    generate(candidate,ROOT/'reports'); state=candidate
    return self.reply(200,json.dumps(state,allow_nan=False).encode())
   except (ValueError,TypeError,KeyError,AttributeError,OverflowError): return self.reply(400,b'{"error":"Invalid HAR structure or metadata. No capture retained."}')
 server=HTTPServer(('127.0.0.1',port),Handler)
 print(f'Site Architecture Lab: http://127.0.0.1:{port}',flush=True)
 try: server.serve_forever()
 except KeyboardInterrupt: server.server_close()

def main():
 parser=argparse.ArgumentParser(description='Offline HAR metadata research. No target requests are made.')
 sub=parser.add_subparsers(dest='command',required=True)
 a=sub.add_parser('analyze'); a.add_argument('har'); a.add_argument('--output',default='reports'); a.add_argument('--synthetic',action='store_true')
 s=sub.add_parser('serve'); s.add_argument('--port',type=int,default=8765)
 args=parser.parse_args()
 if args.command=='serve': serve(args.port)
 else:
  try:
   data=analyze(load(args.har),args.synthetic); generate(data,args.output)
   print(f"Analyzed {data['summary']['total_requests']} requests. Redacted reports: {args.output}")
  except (ValueError,TypeError,KeyError,AttributeError,OSError): parser.exit(2,'Invalid or unreadable HAR; no raw data printed.\n')
if __name__=='__main__': main()
