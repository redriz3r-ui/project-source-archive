"""Convert images and GIF-like media into 53x11 RGB canvases."""

from __future__ import annotations

from .canvas import Canvas


def image_to_canvas(image, fit="contain", background=(0, 0, 0)):
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("image support needs: pip install -e '.[media]'") from exc
    rgba=image.convert("RGBA")
    method=Image.Resampling.NEAREST
    if fit=="cover": resized=ImageOps.fit(rgba,(53,11),method=method)
    else:
        resized=ImageOps.contain(rgba,(53,11),method=method)
        base=Image.new("RGBA",(53,11),(*background,255))
        base.alpha_composite(resized,((53-resized.width)//2,(11-resized.height)//2)); resized=base
    rgb=resized.convert("RGB"); canvas=Canvas(); canvas.pixels[:]=rgb.tobytes()
    return canvas


def media_frames(path, fit="contain"):
    try:
        from PIL import Image, ImageSequence
    except ImportError as exc:
        raise RuntimeError("image support needs: pip install -e '.[media]'") from exc
    with Image.open(path) as image:
        for frame in ImageSequence.Iterator(image):
            yield image_to_canvas(frame,fit=fit),max(.02,float(frame.info.get("duration",100))/1000)

