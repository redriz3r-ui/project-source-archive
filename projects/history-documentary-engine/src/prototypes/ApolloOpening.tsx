import type {CSSProperties} from 'react';
import {Audio} from '@remotion/media';
import {AbsoluteFill, Img, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {apolloOpeningCaptions, apolloOpeningShots, type Shot} from './apolloOpeningPlan';

const ArchiveShot = ({shot}: {shot: Shot}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const progress = interpolate(frame, [0, durationInFrames - 1], [0, 1], {extrapolateRight: 'clamp'});
  const scale = interpolate(progress, [0, 1], [shot.scaleFrom, shot.scaleTo]);
  const transform = `translate(${(shot.translateX ?? 0) * progress}px, ${(shot.translateY ?? 0) * progress}px) scale(${scale})`;
  return <AbsoluteFill style={{background: '#080909', overflow: 'hidden'}}>
    <Img src={staticFile(shot.src)} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: shot.objectPosition, transform, filter: 'contrast(1.08) saturate(.88) brightness(.82)'}} />
    <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(0,0,0,.28), transparent 30%, transparent 66%, rgba(0,0,0,.62))'}} />
    <div style={{position: 'absolute', right: 28, top: 24, color: 'rgba(255,255,255,.78)', fontFamily: 'Arial, sans-serif', fontSize: 13, letterSpacing: 1.5}}>{shot.credit}</div>
  </AbsoluteFill>;
};

const Caption = () => {
  const frame = useCurrentFrame();
  const caption = apolloOpeningCaptions.find((item) => frame >= item.start && frame < item.end);
  if (!caption) return null;
  const style: CSSProperties = {position: 'absolute', left: 120, right: 120, bottom: 48, textAlign: 'center', color: '#fff', fontFamily: 'Arial, sans-serif', fontSize: 31, fontWeight: 700, lineHeight: 1.22, textShadow: '0 2px 5px #000, 0 4px 16px #000'};
  return <div style={style}><span style={{background: 'rgba(0,0,0,.68)', padding: '9px 16px 11px', boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone'}}>{caption.text}</span></div>;
};

export const ApolloOpening = () => {
  const frame = useCurrentFrame();
  const titleOpacity = interpolate(frame, [4, 12, 20, 28], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <AbsoluteFill style={{background: '#080909'}}>
    <Audio src={staticFile('projects/apollo-11-opening/audio/score.wav')} volume={(audioFrame) => audioFrame < 30 ? .035 : .014} />
    <Sequence from={0} durationInFrames={18}><Audio src={staticFile('projects/apollo-11-opening/audio/opening-impact.wav')} volume={.08} /></Sequence>
    <Sequence from={30} durationInFrames={840}><Audio src={staticFile('projects/apollo-11-opening/audio/narration.wav')} volume={1} /></Sequence>
    {apolloOpeningShots.map((shot) => <Sequence key={shot.id} from={shot.start} durationInFrames={shot.duration} name={shot.id}><ArchiveShot shot={shot} /></Sequence>)}
    <AbsoluteFill style={{pointerEvents: 'none', opacity: .035, backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=%220 0 160 160%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cfilter id=%22n%22%3E%3CfeTurbulence type=%22fractalNoise%22 baseFrequency=%22.85%22 numOctaves=%223%22/%3E%3C/filter%3E%3Crect width=%22100%25%22 height=%22100%25%22 filter=%22url(%23n)%22/%3E%3C/svg%3E")', mixBlendMode: 'screen'}} />
    <div style={{position: 'absolute', left: 68, top: 62, opacity: titleOpacity, color: 'white', fontFamily: 'Arial, sans-serif'}}>
      <div style={{fontSize: 18, letterSpacing: 7, fontWeight: 700}}>JULY 1969</div>
      <div style={{fontFamily: 'Georgia, serif', fontSize: 76, fontWeight: 700, letterSpacing: -2}}>APOLLO 11</div>
    </div>
    <Caption />
  </AbsoluteFill>;
};
