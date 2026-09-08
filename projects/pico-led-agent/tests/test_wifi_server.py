import json
import sys
import unittest
import threading
import time
from pathlib import Path

PICO = Path(__file__).parents[1] / "pico_v2"
sys.path.insert(0, str(PICO))
from wifi_server import WifiServer


class FakeClient:
    def __init__(self): self.sent=bytearray()
    def send(self,data): self.sent.extend(data); return len(data)
    def close(self): pass


class FakeRuntime:
    def status(self,now): return {"ok":True,"mode":"idle"}
    def capabilities(self): return {"ok":True,"width":53,"height":11}
    def handle(self,msg,now): return {"ok":True,"cmd":msg.get("cmd")}


def server(token=""):
    value=WifiServer.__new__(WifiServer); value.runtime=FakeRuntime(); value.token=token; value.clients={}
    return value


class WifiServerTests(unittest.TestCase):
    def test_server_refuses_missing_or_weak_token(self):
        with self.assertRaises(ValueError): WifiServer(FakeRuntime(),0,"")
        with self.assertRaises(ValueError): WifiServer(FakeRuntime(),0,"short")

    def test_http_status(self):
        client=FakeClient(); dead=[]
        server()._http(client,b"GET /status HTTP/1.1\r\nHost: pico\r\n\r\n",10,dead)
        self.assertIn(b"200 OK",client.sent); self.assertIn(b'"mode": "idle"',client.sent)

    def test_http_command_and_token(self):
        body=json.dumps({"v":2,"cmd":"status"}).encode()
        request=(b"POST /command HTTP/1.1\r\nX-Agent-Token: secret\r\nContent-Length: "+str(len(body)).encode()+b"\r\n\r\n"+body)
        client=FakeClient(); server("secret")._http(client,request,5,[])
        self.assertIn(b'"cmd": "status"',client.sent)
        denied=FakeClient(); server("secret")._http(denied,b"GET /status HTTP/1.1\r\n\r\n",5,[])
        self.assertIn(b"401 Error",denied.sent)

    def test_masked_websocket_command(self):
        payload=b'{"v":2,"cmd":"status"}'; mask=b"abcd"
        masked=bytes(value^mask[i%4] for i,value in enumerate(payload))
        packet=bytes((129,128|len(payload)))+mask+masked
        client=FakeClient(); ws=server(); ws.clients[client]=b""
        ws._websocket(client,packet,5,[])
        self.assertEqual(client.sent[0],129)
        self.assertIn(b'"cmd": "status"',client.sent)

    def test_real_http_transport_round_trip(self):
        from led_agent.transports import HttpTransport,WebSocketTransport
        token="test-secret-token-123"
        try: service=WifiServer(FakeRuntime(),0,token)
        except PermissionError: self.skipTest("sandbox does not permit local sockets")
        port=service.server.getsockname()[1]; running=[True]
        def serve():
            while running[0]: service.poll(1); time.sleep(.002)
        worker=threading.Thread(target=serve,daemon=True); worker.start()
        try:
            result=HttpTransport(f"127.0.0.1:{port}",token).send({"v":2,"cmd":"status"})
            self.assertEqual(result["cmd"],"status")
            result=WebSocketTransport(f"127.0.0.1:{port}",token).send({"v":2,"cmd":"status"})
            self.assertEqual(result["cmd"],"status")
        finally:
            running[0]=False; worker.join(1)
            for client in list(service.clients): client.close()
            service.server.close()


if __name__=="__main__": unittest.main()
