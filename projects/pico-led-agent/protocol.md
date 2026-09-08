# LED Agent protocol v1

Transport is UTF-8, newline-delimited JSON. Each host message is one object:

```json
{"v":1,"cmd":"play","animation":"eyes","params":{"speed":1.0}}
{"v":1,"cmd":"scroll","text":"HELLO","params":{"speed":1.0}}
{"v":1,"cmd":"setting","name":"brightness","value":4}
{"v":1,"cmd":"stop"}
{"v":1,"cmd":"clear"}
{"v":1,"cmd":"ping"}
```

The Pico replies with exactly one line:

```json
{"ok":true,"message":"playing eyes"}
{"ok":false,"error":"unknown animation"}
```

Unknown fields are ignored. Commands with a protocol version other than `1`
are rejected. This lets future Mac agents talk safely to older firmware.

## Version 2

V2 retains newline-delimited JSON and adds capability discovery, validated
scene programs, and complete RGB frames:

```json
{"v":2,"cmd":"capabilities"}
{"v":2,"cmd":"scene","id":"scene-1","scene":{"v":2,"name":"night","brightness":0.15,"steps":[{"duration":10,"layers":[{"effect":"rain","palette":"cyberpunk"}]}]}}
{"v":2,"cmd":"frame","encoding":"rgb-rle-base64","width":53,"height":11,"data":"..."}
```

Scene messages are limited to 32 KiB, 32 steps, 16 layers per step, and bounded
numeric parameters. Frame RLE is a sequence of four-byte runs:
`count, red, green, blue`, subsequently Base64 encoded for serial JSON. A frame
must decode to exactly 583 RGB pixels. Replies echo `id` when one was supplied.
