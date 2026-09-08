"""Rate-limited RGB frame streaming independent of transport."""

from __future__ import annotations

import time

from .protocol_v2 import frame_message


class FrameStreamer:
    def __init__(self, transport, fps=15, clock=time.monotonic, sleeper=time.sleep):
        self.transport, self.fps = transport, max(1, min(30, fps))
        self.clock, self.sleeper = clock, sleeper

    def stream(self, frames, duration=None):
        started = deadline = self.clock()
        sent = 0
        for frame in frames:
            if duration is not None and self.clock() - started >= duration: break
            self.transport.send(frame_message(frame, f"frame-{sent}"))
            sent += 1
            deadline += 1 / self.fps
            wait = deadline - self.clock()
            if wait > 0: self.sleeper(wait)
        return sent

    def stream_timed(self, timed_frames, loops=1):
        frames=list(timed_frames); sent=0
        for _ in range(max(1,loops)):
            for frame,duration in frames:
                self.transport.send(frame_message(frame,f"frame-{sent}")); sent+=1
                self.sleeper(max(.02,float(duration)))
        return sent
