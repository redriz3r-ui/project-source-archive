import math
import unittest

from led_agent.audio import AudioAnalyzer, SpectrumRenderer
from led_agent.canvas import Canvas
from led_agent.streaming import FrameStreamer


class FakeTransport:
    def __init__(self): self.messages=[]
    def send(self,message): self.messages.append(message); return {"ok":True}


class AudioStreamingTests(unittest.TestCase):
    def test_analyzer_finds_signal_and_returns_bounded_bands(self):
        samples=[math.sin(2*math.pi*440*n/8000) for n in range(512)]
        result=AudioAnalyzer(8000,8).analyze(samples)
        self.assertEqual(len(result["bands"]),8)
        self.assertTrue(all(0<=x<=1 for x in result["bands"]))
        self.assertGreater(result["energy"],0)

    def test_spectrum_is_hardware_sized(self):
        frame=SpectrumRenderer().render({"bands":[.2,.8,1],"beat":1})
        self.assertEqual(len(frame.pixels),53*11*3)
        self.assertTrue(any(frame.pixels))

    def test_streamer_sends_frames(self):
        transport=FakeTransport(); ticks=iter((0,0,.1,.1,.2,.2,.3))
        streamer=FrameStreamer(transport,fps=10,clock=lambda:next(ticks),sleeper=lambda _:None)
        self.assertEqual(streamer.stream([Canvas(),Canvas()]),2)
        self.assertEqual(len(transport.messages),2)

    def test_timed_media_stream(self):
        transport=FakeTransport(); delays=[]
        streamer=FrameStreamer(transport,sleeper=delays.append)
        self.assertEqual(streamer.stream_timed([(Canvas(),.08),(Canvas(),.12)],loops=2),4)
        self.assertEqual(delays,[.08,.12,.08,.12])


if __name__=="__main__": unittest.main()
