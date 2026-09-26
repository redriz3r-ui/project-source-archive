import copy
import unittest
import tempfile
from pathlib import Path
import cv2
import numpy as np
from src.scene_detection import detect
from src.reframer import crop_track
from src.reel_director import build_plan, validate_plan
from src.shot_ranker import eligible
from src.utils import config


def library():
    return [{'shot_id': i+1, 'start': i*100., 'end': i*100.+6, 'duration': 6,
             'faces': i%3, 'face_fraction': (i%3)/2, 'visual_interest': .6, 'composition_score': .7,
             'motion_score': (i%7)/7, 'darkness': .3, 'colorfulness': .6, 'stability': .6,
             'mean_color': [(i%5)/5,.5,.3], 'primary_subject': [.5,.5], 'tracking': []} for i in range(50)]


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.cfg, self.shots = config(), library()

    def test_duration_boundaries_and_variant_diversity(self):
        request = {'duration': 22, 'mood': 'dreamy romantic', 'aspect': '9:16', 'spoilers': 'low', 'audio': 'muted'}
        prior = set()
        for i in range(3):
            plan = build_plan(self.shots, {'duration':5000}, self.cfg, request, i, prior, f'reel_{i}')
            self.assertAlmostEqual(sum(s['duration'] for s in plan['shots']), 22)
            validate_plan(plan, self.shots, self.cfg)
            ids = {s['shot_id'] for s in plan['shots']}
            self.assertLessEqual(len(ids & prior), len(ids)/2)
            self.assertEqual(len(ids), len(plan['shots']))
            prior.update(ids)

    def test_excluded_range_overlap(self):
        result = eligible(self.shots, 5000, 'unrestricted', self.cfg, [[103,104]])
        self.assertNotIn(2, {s['shot_id'] for s in result})

    def test_pan_speed_deadzone_and_clamp(self):
        shot = copy.deepcopy(self.shots[0])
        shot['tracking'] = [{'time': i/2, 'center': [.2+i*.08,.5], 'faces': []} for i in range(8)]
        _, points = crop_track(shot, {'source_in':0,'duration':4,'crop_mode':'smart_crop'},9/16,16/9,self.cfg)
        for a,b in zip(points,points[1:]):
            self.assertLessEqual(abs(b['center'][0]-a['center'][0]),(b['time']-a['time'])*.08+1e-8)
        self.assertGreater(points[-1]['center'][0],.2)
        shot['tracking'] = [{'time':i/2,'center':[.5+i*.001,.5],'faces':[]} for i in range(8)]
        _,points = crop_track(shot,{'source_in':0,'duration':4},9/16,16/9,self.cfg)
        self.assertTrue(all(p['center']==points[0]['center'] for p in points))

    def test_auto_preserves_two_separated_faces(self):
        shot = copy.deepcopy(self.shots[0])
        shot['faces'] = 2
        shot['tracking'] = [{'time':0,'center':[.2,.5],'faces':[[.1,.3,.1,.2],[.8,.3,.1,.2]]}]
        mode,_ = crop_track(shot,{'source_in':0,'duration':2},9/16,16/9,self.cfg)
        self.assertEqual(mode,'blur_background')

    def test_single_frame_flashes_do_not_create_cuts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            movie = path / 'flashes.mp4'
            writer = cv2.VideoWriter(str(movie),cv2.VideoWriter_fourcc(*'mp4v'),12,(160,90))
            for i in range(60):
                frame = np.full((90,160,3),(20,30,200),dtype=np.uint8)
                if i in (15,30,45):
                    frame[:] = 255
                writer.write(frame)
            writer.release()
            shots,_ = detect(path,{'proxy':str(movie),'proxy_key':'fixture','duration':5},self.cfg)
            self.assertEqual(len(shots),1)

    def test_continuous_segment_setting_changes_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            movie = path / 'continuous.mp4'
            writer = cv2.VideoWriter(str(movie), cv2.VideoWriter_fourcc(*'mp4v'), 12, (160,90))
            for _ in range(36 * 12):
                writer.write(np.full((90,160,3), 80, dtype=np.uint8))
            writer.release()
            film = {'proxy':str(movie), 'proxy_key':'continuous-fixture', 'duration':36}
            self.cfg['analysis']['continuous_segment_seconds'] = 6
            short, _ = detect(path, film, self.cfg)
            self.cfg['analysis']['continuous_segment_seconds'] = 9
            long, _ = detect(path, film, self.cfg)
            self.assertEqual(len(short), 6)
            self.assertEqual(len(long), 4)

    def test_audio_volume_saved_and_validated(self):
        request = {'duration': 5, 'mood': 'quiet', 'aspect': '9:16', 'spoilers': 'low',
                   'audio': 'original', 'audio_volume': 1.5}
        plan = build_plan(self.shots, {'duration':5000}, self.cfg, request, 0, set(), 'volume')
        self.assertEqual(plan['audio_volume'], 1.5)
        plan['audio_volume'] = 2.1
        with self.assertRaisesRegex(ValueError, 'Audio volume'):
            validate_plan(plan, self.shots, self.cfg)

    def test_missed_first_face_does_not_initialize_on_background(self):
        shot = copy.deepcopy(self.shots[0])
        shot['faces'] = 1
        shot['tracking'] = [
            {'time': 0, 'center': [.2,.5], 'faces': []},
            {'time': .5, 'center': [.7,.4], 'faces': [[.65,.2,.1,.2]]},
            {'time': 1, 'center': [.7,.4], 'faces': [[.65,.2,.1,.2]]}]
        _, points = crop_track(shot, {'source_in':0,'duration':2,'crop_mode':'smart_crop'}, 9/16,16/9,self.cfg)
        self.assertAlmostEqual(points[0]['center'][0],.7)

    def test_small_library_uses_available_capacity(self):
        shots = library()[:3]
        for shot in shots:
            shot['duration'] = 3
            shot['end'] = shot['start'] + 3
        request = {'duration': 8, 'mood': 'fast', 'aspect': '9:16', 'spoilers': 'unrestricted', 'audio': 'muted'}
        plan = build_plan(shots, {'duration': 5000}, self.cfg, request, 0, set(), 'short')
        self.assertAlmostEqual(sum(s['duration'] for s in plan['shots']), 8)

    def test_changed_boundaries_reject_stale_plan(self):
        request = {'duration': 5, 'mood': 'quiet', 'aspect': '9:16', 'spoilers': 'low', 'audio': 'muted'}
        plan = build_plan(self.shots, {'duration': 5000}, self.cfg, request, 0, set(), 'stale')
        self.shots[0]['end'] += 1
        with self.assertRaisesRegex(ValueError, 'boundaries differ'):
            validate_plan(plan, self.shots, self.cfg)

    def test_invalid_plan_rejected(self):
        request={'duration':5,'mood':'quiet','aspect':'9:16','spoilers':'low','audio':'muted'}
        plan=build_plan(self.shots,{'duration':5000},self.cfg,request,0,set(),'test')
        plan['shots'][0]['source_in']=100
        with self.assertRaises(ValueError):
            validate_plan(plan,self.shots,self.cfg)

if __name__=='__main__':
    unittest.main()
