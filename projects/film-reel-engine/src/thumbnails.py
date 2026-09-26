from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps


def contact_sheets(shots: list[dict], project: Path, prefix: str = 'contact', columns: int = 4, rows: int = 6) -> list[str]:
    paths = []
    for page, begin in enumerate(range(0, len(shots), columns * rows), 1):
        subset = shots[begin:begin + columns * rows]
        sheet = Image.new('RGB', (columns * 256, ((len(subset) + columns - 1) // columns) * 170), '#151515')
        draw = ImageDraw.Draw(sheet)
        for i, shot in enumerate(subset):
            x, y = i % columns * 256, i // columns * 170
            with Image.open(project / shot['thumbnail']) as image:
                thumb = ImageOps.contain(image, (252, 140))
                sheet.paste(thumb, (x + (256 - thumb.width) // 2, y))
            seconds = int(shot['start'])
            draw.text((x + 6, y + 144), f"#{shot['shot_id']:04d}   {seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}", fill='white')
        path = project / 'thumbnails' / f'{prefix}_{page:03d}.jpg'
        sheet.save(path, quality=88)
        paths.append(str(path.relative_to(project)))
    return paths
