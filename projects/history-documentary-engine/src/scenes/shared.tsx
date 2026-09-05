import type {CSSProperties, ReactNode} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

export const colors = {ink: '#171713', paper: '#e7dfcb', accent: '#9f382d'};

export const FilmFrame = ({children, caption, credit}: {children: ReactNode; caption?: string; credit?: string}) => {
  const frame = useCurrentFrame();
  const grain = 0.045 + (frame % 3) * 0.012;
  return <AbsoluteFill style={{background: colors.ink, color: colors.paper, overflow: 'hidden', fontFamily: 'Georgia, serif'}}>
    {children}
    <AbsoluteFill style={{pointerEvents: 'none', opacity: grain, backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=%220 0 180 180%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cfilter id=%22n%22%3E%3CfeTurbulence type=%22fractalNoise%22 baseFrequency=%220.9%22 numOctaves=%224%22 stitchTiles=%22stitch%22/%3E%3C/filter%3E%3Crect width=%22100%25%22 height=%22100%25%22 filter=%22url(%23n)%22 opacity=%22.55%22/%3E%3C/svg%3E")', mixBlendMode: 'screen'}} />
    {caption ? <div style={{position: 'absolute', left: 76, right: 76, bottom: 58, fontSize: 32, lineHeight: 1.25, textShadow: '0 2px 10px #000', borderLeft: `5px solid ${colors.accent}`, paddingLeft: 22}}>{caption}</div> : null}
    {credit ? <div style={{position: 'absolute', left: 360, right: 28, top: 24, fontFamily: 'Arial, sans-serif', fontSize: 14, letterSpacing: 1.4, opacity: .72, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textAlign: 'right'}}>{credit.toUpperCase()}</div> : null}
  </AbsoluteFill>;
};

export const useEntrance = (): CSSProperties => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return {opacity: interpolate(frame, [0, fps * .45], [0, 1], {extrapolateRight: 'clamp'}), transform: `translateY(${interpolate(frame, [0, fps * .6], [24, 0], {extrapolateRight: 'clamp'})}px)`};
};
