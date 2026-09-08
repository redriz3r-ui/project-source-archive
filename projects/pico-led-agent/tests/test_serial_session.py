import json
import unittest

from led_agent.transports import SerialTransport


class FakeConnection:
    opens=0
    def __init__(self,*_args,**_kwargs): type(self).opens+=1; self.writes=[]
    def reset_input_buffer(self): pass
    def write(self,data): self.writes.append(data)
    def flush(self): pass
    def readline(self): return b'{"ok":true}\n'
    def close(self): pass


class FakeSerialModule:
    SerialException=Exception
    Serial=FakeConnection


class SerialSessionTests(unittest.TestCase):
    def test_session_reuses_one_connection(self):
        transport=SerialTransport.__new__(SerialTransport)
        transport._serial_module=FakeSerialModule; transport.port="fake"; transport.baudrate=115200; transport.timeout=1
        FakeConnection.opens=0
        with transport.session() as session:
            self.assertTrue(session.send({"v":2,"cmd":"status"})["ok"])
            self.assertTrue(session.send({"v":2,"cmd":"status"})["ok"])
        self.assertEqual(FakeConnection.opens,1)


if __name__=="__main__": unittest.main()
