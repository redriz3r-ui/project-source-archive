from __future__ import annotations

import argparse
import json
import sys
from contextlib import nullcontext

from .compiler import compile_prompt
from .parser import ParseError, parse
from .presets import PresetStore
from .protocol_v2 import scene_message
from .transports import HttpTransport, SimulatorTransport, SerialTransport, TransportError, WebSocketTransport, likely_ports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Control a Pico W LED matrix with plain English")
    parser.add_argument("command", nargs="*", help="for example: show blinking eyes")
    parser.add_argument("--transport", choices=("serial", "wifi", "websocket", "sim"), default="serial")
    parser.add_argument("--port", help="USB serial port; auto-detected when possible")
    parser.add_argument("--host", help="Pico IP or hostname for Wi-Fi transport")
    parser.add_argument("--token", default="", help="Wi-Fi API token")
    parser.add_argument("--list-ports", action="store_true")
    parser.add_argument("--preview", action="store_true", help="preview a rich v2 scene on the Mac")
    parser.add_argument("--web-preview", metavar="PATH", help="write an interactive browser preview")
    parser.add_argument("--v2", action="store_true", help="compile and send a rich v2 scene")
    parser.add_argument("--save", metavar="NAME", help="save the compiled v2 scene")
    parser.add_argument("--preset", metavar="NAME", help="send a previously saved v2 scene")
    parser.add_argument("--save-playlist", metavar="NAME", help="save positional preset names as a playlist")
    parser.add_argument("--playlist", metavar="NAME", help="send a saved playlist")
    parser.add_argument("--list-presets", action="store_true")
    parser.add_argument("--presets-file", default="presets.json")
    parser.add_argument("--status", action="store_true", help="show v2 device status")
    parser.add_argument("--capabilities", action="store_true", help="show v2 device capabilities")
    parser.add_argument("--stream-media", metavar="PATH", help="stream an image or animated GIF")
    parser.add_argument("--media-loops", type=int, default=1)
    parser.add_argument("--audio-reactive", nargs="?", type=float, const=30, metavar="SECONDS")
    return parser


def choose_transport(args):
    if args.transport == "sim":
        return SimulatorTransport()
    if args.transport == "wifi":
        if not args.host:
            raise TransportError("Wi-Fi transport needs --host")
        return HttpTransport(args.host, args.token)
    if args.transport == "websocket":
        if not args.host: raise TransportError("WebSocket transport needs --host")
        return WebSocketTransport(args.host,args.token)
    port = args.port
    if not port:
        ports = likely_ports()
        if len(ports) != 1:
            shown = ", ".join(ports) if ports else "none found"
            raise TransportError(f"Choose a port with --port. Available ports: {shown}")
        port = ports[0]
    return SerialTransport(port)


def run_one(text, transport) -> bool:
    try:
        command = parse(text).to_wire()
        response = transport.send(command)
    except (ParseError, TransportError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return False
    print(response.get("message") or response.get("error") or json.dumps(response))
    return bool(response.get("ok"))


def run_v2(scene, transport) -> bool:
    try:
        response = transport.send(scene_message(scene))
    except (ValueError, TransportError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return False
    print(response.get("message") or response.get("error") or json.dumps(response))
    return bool(response.get("ok"))


def main() -> None:
    args = build_parser().parse_args()
    if args.list_ports:
        try:
            print("\n".join(likely_ports()) or "No serial ports found.")
        except TransportError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(2)
        return
    if args.preview:
        if not args.command:
            print("Error: --preview needs a scene description", file=sys.stderr)
            raise SystemExit(2)
        from .simulator import preview
        preview(compile_prompt(" ".join(args.command)))
        return
    if args.web_preview:
        if not args.command:
            print("Error: --web-preview needs a scene description",file=sys.stderr); raise SystemExit(2)
        from .web_preview import build_preview
        print(build_preview(compile_prompt(" ".join(args.command)),args.web_preview))
        return
    store = PresetStore(args.presets_file)
    if args.list_presets:
        data=store.load()
        print("Scenes:",", ".join(sorted(data["scenes"])) or "none")
        print("Playlists:",", ".join(sorted(data["playlists"])) or "none")
        return
    if args.save_playlist:
        if not args.command:
            print("Error: --save-playlist needs preset names",file=sys.stderr); raise SystemExit(2)
        try: store.save_playlist(args.save_playlist,args.command)
        except ValueError as exc: print(f"Error: {exc}",file=sys.stderr); raise SystemExit(2)
        print(f"saved playlist {args.save_playlist}"); return
    if args.save:
        if not args.command:
            print("Error: --save needs a scene description", file=sys.stderr)
            raise SystemExit(2)
        scene = compile_prompt(" ".join(args.command))
        store.save_scene(args.save, scene)
        print(f"saved {args.save}")
        return
    try:
        transport = choose_transport(args)
    except TransportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2)
    if args.status or args.capabilities:
        command={"v":2,"cmd":"status" if args.status else "capabilities"}
        try: print(json.dumps(transport.send(command),indent=2))
        except TransportError as exc: print(f"Error: {exc}",file=sys.stderr); raise SystemExit(1)
        return
    if args.stream_media:
        from .media import media_frames
        from .streaming import FrameStreamer
        context=transport.session() if hasattr(transport,"session") else nullcontext(transport)
        try:
            with context as streaming_transport:
                count=FrameStreamer(streaming_transport).stream_timed(media_frames(args.stream_media),args.media_loops)
        except (OSError,RuntimeError,TransportError) as exc: print(f"Error: {exc}",file=sys.stderr); raise SystemExit(1)
        print(f"streamed {count} frames")
        return
    if args.audio_reactive is not None:
        _run_audio(transport,args.audio_reactive)
        return
    if args.preset:
        try:
            scene = store.get_scene(args.preset)
        except (KeyError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(2)
        raise SystemExit(0 if run_v2(scene, transport) else 1)
    if args.playlist:
        try: scene=store.get_playlist_scene(args.playlist)
        except (KeyError,ValueError) as exc: print(f"Error: {exc}",file=sys.stderr); raise SystemExit(2)
        raise SystemExit(0 if run_v2(scene,transport) else 1)
    if args.command and args.v2:
        raise SystemExit(0 if run_v2(compile_prompt(" ".join(args.command)), transport) else 1)
    if args.command:
        raise SystemExit(0 if run_one(" ".join(args.command), transport) else 1)
    print("Pico LED agent. Type 'quit' to leave.")
    while True:
        try:
            text = input("led> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text.strip().lower() in ("quit", "exit"):
            break
        if args.v2:
            try: run_v2(compile_prompt(text), transport)
            except ValueError as exc: print(f"Error: {exc}", file=sys.stderr)
        else:
            run_one(text, transport)


def _run_audio(transport,seconds):
    import queue, time
    from .audio import AudioAnalyzer, MicrophoneSource, SpectrumRenderer
    from .protocol_v2 import frame_message
    blocks=queue.Queue(maxsize=3); analyzer=AudioAnalyzer(); renderer=SpectrumRenderer()
    def receive(samples,status):
        if status: print(status,file=sys.stderr)
        try: blocks.put_nowait(list(samples))
        except queue.Full: pass
    deadline=time.monotonic()+max(1,seconds); sent=0
    context=transport.session() if hasattr(transport,"session") else nullcontext(transport)
    try:
        with context as streaming_transport, MicrophoneSource(receive):
            while time.monotonic()<deadline:
                try: samples=blocks.get(timeout=.5)
                except queue.Empty: continue
                streaming_transport.send(frame_message(renderer.render(analyzer.analyze(samples)),f"audio-{sent}")); sent+=1
    except (RuntimeError,TransportError) as exc:
        print(f"Error: {exc}",file=sys.stderr); raise SystemExit(1)
    print(f"streamed {sent} audio-reactive frames")


if __name__ == "__main__":
    main()
