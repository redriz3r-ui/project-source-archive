import {Audio} from '@remotion/media';
import {AbsoluteFill, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {DocumentaryManifest} from './manifest/schema';
import {RegisteredScene} from './scenes/registry';
import {CaptionOverlay} from './captions/CaptionOverlay';

const DirectedScene = ({scene}: {scene: DocumentaryManifest['scenes'][number]}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const transition = scene.direction?.transition ?? 'CUT';
  const fadeFrames = transition === 'CUT' ? 2 : 10;
  const opacity = transition === 'CUT' ? 1 : interpolate(frame, [0, fadeFrames, durationInFrames - fadeFrames, durationInFrames], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const motion = scene.direction?.motion;
  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {extrapolateRight: 'clamp'});
  const transform = motion === 'PAN_LEFT' ? `translateX(${14 - progress * 28}px) scale(1.04)` : motion === 'PAN_RIGHT' ? `translateX(${-14 + progress * 28}px) scale(1.04)` : motion === 'PULL_OUT' ? `scale(${1.07 - progress * .07})` : motion === 'FLOAT' ? `translateY(${8 - progress * 16}px) scale(1.03)` : motion === 'PUSH_IN' ? `scale(${1 + progress * .07})` : 'none';
  return <AbsoluteFill style={{opacity, transform}}><RegisteredScene scene={scene} /></AbsoluteFill>;
};

export const Documentary = ({manifest}: {manifest: DocumentaryManifest}) => <AbsoluteFill>
  {manifest.soundtrack ? <Audio src={staticFile(manifest.soundtrack.src)} volume={(frame) => manifest.scenes.some((scene) => scene.audio && frame >= scene.startFrame && frame < scene.startFrame + scene.durationFrames) ? manifest.soundtrack!.duckVolume : manifest.soundtrack!.baseVolume} /> : null}
  {manifest.soundEffects.map((cue) => <Sequence key={cue.id} from={cue.startFrame} durationInFrames={30}><Audio src={staticFile(cue.src)} volume={cue.volume} /></Sequence>)}
  {manifest.scenes.map((scene) => <Sequence key={scene.id} from={scene.startFrame} durationInFrames={scene.durationFrames} name={`${scene.type}: ${scene.id}`}>
    <DirectedScene scene={scene} />
    {scene.audio ? <Audio src={staticFile(scene.audio.src)} /> : null}
    <CaptionOverlay scene={scene} />
  </Sequence>)}
</AbsoluteFill>;
