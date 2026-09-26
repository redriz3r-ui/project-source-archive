from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def draw_card(path: Path, width: int, height: int, card: dict) -> None:
    image = Image.new('RGB', (width, height), card.get('background', '#0c1014'))
    draw = ImageDraw.Draw(image)
    fonts = [card.get('font', ''), '/System/Library/Fonts/Supplemental/Arial.ttf',
             '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    font_path = next((p for p in fonts if p and Path(p).is_file()), None)
    lines = [str(s) for s in card.get('lines', [])]
    if not lines:
        raise ValueError('Enabled end card needs at least one text line')
    size = max(12, int(width * 0.065))
    while True:
        font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default(size=size)
        boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
        line_height = size * 1.5
        if (max(b[2] - b[0] for b in boxes) <= width * 0.84 and len(lines) * line_height <= height * 0.8) or size <= 8:
            break
        size -= 1
    for i, (line, box) in enumerate(zip(lines, boxes)):
        x = (width - (box[2] - box[0])) / 2 - box[0]
        y = height / 2 - len(lines) * line_height / 2 + i * line_height - box[1]
        draw.text((x, y), line, font=font, fill=card.get('color', 'white'))
    image.save(path)
