"""Tiny non-blocking HTTP + WebSocket JSON server for MicroPython."""

import json, socket
try:
    import ubinascii as binascii
except ImportError:
    import binascii
try:
    import uhashlib as hashlib
except ImportError:
    import hashlib

GUID="258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WifiServer:
    def __init__(self,runtime,port=80,token=""):
        if not token or len(token)<16: raise ValueError("Wi-Fi API token must be at least 16 characters")
        self.runtime,self.token=runtime,token
        self.server=socket.socket(); self.server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        self.server.bind(("0.0.0.0",int(port))); self.server.listen(3); self.server.setblocking(False)
        self.clients={}

    def poll(self,now):
        try:
            client,_=self.server.accept(); client.setblocking(False); self.clients[client]=bytearray()
        except OSError: pass
        dead=[]
        for client,state in list(self.clients.items()):
            try: chunk=client.recv(4096)
            except OSError: continue
            if not chunk: dead.append(client); continue
            if isinstance(state,bytearray):
                state.extend(chunk)
                if len(state)>32768: dead.append(client); continue
                if b"\r\n\r\n" in state:
                    try: self._http(client,bytes(state),now,dead)
                    except Exception as exc:
                        try: self._reply_http(client,{"ok":False,"error":"bad request"},400)
                        except Exception: pass
                        dead.append(client)
            else:
                try: self._websocket(client,state+chunk,now,dead)
                except Exception: dead.append(client)
        for client in dead:
            try: client.close()
            except Exception: pass
            self.clients.pop(client,None)

    def _http(self,client,data,now,dead):
        head,body=data.split(b"\r\n\r\n",1); lines=head.decode().split("\r\n")
        method,path,_=lines[0].split(" ",2)
        headers={k.strip().lower():v.strip() for k,v in (line.split(":",1) for line in lines[1:] if ":" in line)}
        if self.token and headers.get("x-agent-token")!=self.token:
            self._reply_http(client,{"ok":False,"error":"unauthorized"},401); dead.append(client); return
        if headers.get("upgrade","").lower()=="websocket":
            key=headers.get("sec-websocket-key","")
            accept=binascii.b2a_base64(hashlib.sha1((key+GUID).encode()).digest()).decode().strip()
            client.send(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: "+accept+"\r\n\r\n").encode())
            self.clients[client]=b""; return
        if method=="GET" and path=="/status": result=self.runtime.status(now)
        elif method=="GET" and path=="/capabilities": result=self.runtime.capabilities()
        elif method=="POST" and path=="/command":
            length=int(headers.get("content-length",0))
            if len(body)<length: self.clients[client]=bytearray(data); return
            try: result=self.runtime.handle(json.loads(body[:length]),now)
            except Exception as exc: result={"ok":False,"error":str(exc)}
        else: result={"ok":False,"error":"not found"}
        self._reply_http(client,result,200 if result.get("ok") else 400); dead.append(client)

    def _reply_http(self,client,result,status):
        body=json.dumps(result).encode(); label="OK" if status==200 else "Error"
        client.send(("HTTP/1.1 %d %s\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n"%(status,label,len(body))).encode()+body)

    def _websocket(self,client,data,now,dead):
        if len(data)<2: self.clients[client]=data; return
        opcode=data[0]&15; masked=data[1]&128; length=data[1]&127; pos=2
        if length==126:
            if len(data)<4: self.clients[client]=data; return
            length=(data[2]<<8)|data[3]; pos=4
        if length>32768: dead.append(client); return
        if masked:
            if len(data)<pos+4+length: self.clients[client]=data; return
            mask=data[pos:pos+4]; pos+=4
        elif len(data)<pos+length: self.clients[client]=data; return
        payload=bytearray(data[pos:pos+length])
        if masked:
            for i in range(length): payload[i]^=mask[i%4]
        if opcode==8: dead.append(client); return
        try: result=self.runtime.handle(json.loads(payload),now)
        except Exception as exc: result={"ok":False,"error":str(exc)}
        self._send_ws(client,json.dumps(result).encode())
        self.clients[client]=data[pos+length:]

    def _send_ws(self,client,payload):
        if len(payload)<126: header=bytes((129,len(payload)))
        else: header=bytes((129,126,len(payload)>>8,len(payload)&255))
        client.send(header+payload)
