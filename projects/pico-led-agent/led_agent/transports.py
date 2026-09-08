from __future__ import annotations

import json
import base64
import hashlib
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from typing import Any


class TransportError(RuntimeError):
    pass


class SerialTransport:
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 2.0):
        try:
            import serial
        except ImportError as exc:
            raise TransportError("USB support needs: python -m pip install -e '.[serial]'") from exc
        self._serial_module = serial
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

    def send(self, command: dict[str, Any]) -> dict[str, Any]:
        with self.session() as connection:
            return connection.send(command)

    def session(self):
        return SerialSession(self)


class SerialSession:
    def __init__(self, transport):
        self.transport, self.connection = transport, None

    def __enter__(self):
        try:
            self.connection=self.transport._serial_module.Serial(
                self.transport.port,self.transport.baudrate,timeout=self.transport.timeout,
                write_timeout=self.transport.timeout)
            time.sleep(.15); self.connection.reset_input_buffer()
        except self.transport._serial_module.SerialException as exc:
            raise TransportError(f"Could not use {self.transport.port}: {exc}") from exc
        return self

    def __exit__(self,*_args):
        if self.connection: self.connection.close()

    def send(self, command: dict[str, Any]) -> dict[str, Any]:
        payload = (json.dumps(command, separators=(",", ":")) + "\n").encode()
        try:
            self.connection.write(payload); self.connection.flush(); line=self.connection.readline()
        except self.transport._serial_module.SerialException as exc:
            raise TransportError(f"Could not use {self.transport.port}: {exc}") from exc
        if not line:
            raise TransportError("The Pico did not reply. Check main.py, the port, and the USB cable.")
        try:
            return json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TransportError(f"Unexpected Pico reply: {line!r}") from exc


class SimulatorTransport:
    def send(self, command: dict[str, Any]) -> dict[str, Any]:
        from .visuals import preview

        print(json.dumps(command, indent=2))
        preview(command, stream=sys.stdout)
        return {"ok": True, "message": "simulated"}


class HttpTransport:
    def __init__(self, host: str, token: str = "", timeout: float = 3.0):
        self.url = "http://" + host.strip().rstrip("/") + "/command"
        self.token, self.timeout = token, timeout

    def send(self, command: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(command, separators=(",", ":")).encode()
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-Agent-Token"] = self.token
        request = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise TransportError(f"Wi-Fi request failed: {exc}") from exc


class WebSocketTransport:
    def __init__(self,host: str,token: str="",timeout: float=3.0):
        self.host,self.token,self.timeout=host.strip().rstrip("/"),token,timeout

    def send(self,command):
        with self.session() as connection: return connection.send(command)

    def session(self): return WebSocketSession(self)


class WebSocketSession:
    def __init__(self,transport): self.transport,self.socket=transport,None

    def __enter__(self):
        host,separator,port=self.transport.host.partition(":")
        port=int(port) if separator else 80
        try:
            self.socket=socket.create_connection((host,port),self.transport.timeout)
            key=base64.b64encode(os.urandom(16)).decode()
            token=f"X-Agent-Token: {self.transport.token}\r\n" if self.transport.token else ""
            request=(f"GET /ws HTTP/1.1\r\nHost: {self.transport.host}\r\nUpgrade: websocket\r\n"
                     f"Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: {key}\r\n{token}\r\n")
            self.socket.sendall(request.encode()); response=self.socket.recv(4096)
            expected=base64.b64encode(hashlib.sha1((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
            if b"101 Switching Protocols" not in response or expected not in response: raise TransportError("WebSocket handshake rejected")
        except (OSError,ValueError) as exc: raise TransportError(f"WebSocket connection failed: {exc}") from exc
        return self

    def __exit__(self,*_args):
        if self.socket:
            try: self.socket.close()
            except OSError: pass

    def send(self,command):
        payload=json.dumps(command,separators=(",",":")).encode(); mask=os.urandom(4)
        if len(payload)<126: header=bytes((129,128|len(payload)))
        elif len(payload)<=65535: header=bytes((129,254,len(payload)>>8,len(payload)&255))
        else: raise TransportError("WebSocket message is too large")
        masked=bytes(value^mask[i%4] for i,value in enumerate(payload))
        try:
            self.socket.sendall(header+mask+masked); first=self._read_exact(2)
            length=first[1]&127
            if length==126:
                extra=self._read_exact(2); length=(extra[0]<<8)|extra[1]
            elif length==127: raise TransportError("oversized WebSocket reply")
            data=self._read_exact(length)
            return json.loads(data)
        except (OSError,json.JSONDecodeError) as exc: raise TransportError(f"WebSocket request failed: {exc}") from exc

    def _read_exact(self,count):
        output=bytearray()
        while len(output)<count:
            chunk=self.socket.recv(count-len(output))
            if not chunk: raise TransportError("WebSocket closed unexpectedly")
            output.extend(chunk)
        return bytes(output)


def likely_ports() -> list[str]:
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise TransportError("Port discovery needs: python -m pip install -e '.[serial]'") from exc
    ports = list(list_ports.comports())
    likely = [p.device for p in ports if "usb" in p.device.lower() or "pico" in (p.description or "").lower()]
    return likely or [p.device for p in ports]
