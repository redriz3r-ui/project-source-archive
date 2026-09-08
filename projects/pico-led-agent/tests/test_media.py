import tempfile
import unittest
from pathlib import Path

from PIL import Image

from led_agent.media import image_to_canvas, media_frames


class MediaTests(unittest.TestCase):
    def test_image_maps_to_hardware_canvas(self):
        image=Image.new("RGB",(4,4),(255,0,0))
        canvas=image_to_canvas(image)
        self.assertEqual((canvas.width,canvas.height),(53,11))
        self.assertIn((255,0,0),(canvas.get(x,5) for x in range(53)))

    def test_animated_gif_yields_timed_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"test.gif"
            frames=[Image.new("RGB",(2,2),color) for color in ((255,0,0),(0,0,255))]
            frames[0].save(path,save_all=True,append_images=frames[1:],duration=80,loop=0)
            output=list(media_frames(path))
            self.assertEqual(len(output),2)
            self.assertEqual(len(output[0][0].pixels),53*11*3)
            self.assertGreaterEqual(output[0][1],.02)


if __name__=="__main__": unittest.main()
