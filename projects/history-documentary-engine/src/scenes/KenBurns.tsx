import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../manifest/schema';
import {FilmFrame} from './shared';

type KenBurnsScene = Extract<Scene, {type: 'KEN_BURNS'}>;
export const KenBurns = ({scene}: {scene: KenBurnsScene}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const p = interpolate(frame, [0, durationInFrames - 1], [0, 1], {extrapolateRight: 'clamp'});
  const {zoomFrom, zoomTo, panX, panY, focalPoint} = scene.payload;
  const scale = zoomFrom + (zoomTo - zoomFrom) * p;
  return <FilmFrame caption={scene.captions?.length ? undefined : scene.caption} credit={scene.payload.credit}>
    <AbsoluteFill style={{transform: `scale(${scale}) translate(${panX * p}px, ${panY * p}px)`, transformOrigin: `${(focalPoint?.x ?? .5) * 100}% ${(focalPoint?.y ?? .5) * 100}%`}}>
      <Img src={staticFile(scene.payload.src)} alt={scene.payload.alt} style={{width: '100%', height: '100%', objectFit: 'cover', filter: 'contrast(1.08) saturate(.82) brightness(.82)'}} />
    </AbsoluteFill>
    <AbsoluteFill style={{background:'linear-gradient(180deg, rgba(0,0,0,.2), transparent 30%, transparent 64%, rgba(0,0,0,.48))'}} />
  </FilmFrame>;
};
