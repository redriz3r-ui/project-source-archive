import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../manifest/schema';
import {colors, FilmFrame} from './shared';

type MapSceneType = Extract<Scene, {type: 'MAP'}>;
const pathFromRoute = (route: number[], width: number, height: number) => route.reduce((d, value, index) => index % 2 === 0 ? `${d}${index === 0 ? 'M' : ' L'} ${value * width}` : `${d} ${value * height}`, '');

export const MapScene = ({scene}: {scene: MapSceneType}) => {
  const frame = useCurrentFrame();
  const {durationInFrames, width, height} = useVideoConfig();
  const progress = interpolate(frame, [12, durationInFrames - 15], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const route = scene.payload.route;
  const space = /\b(moon|lunar|apollo|orbit)\b/i.test(`${scene.payload.region ?? ''} ${scene.payload.label}`);
  return <FilmFrame caption={scene.captions?.length ? undefined : scene.caption}>
    <AbsoluteFill style={{background: space ? '#0d1420' : colors.paper}}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="100%">
        <defs><filter id="rough"><feTurbulence baseFrequency=".014" numOctaves="3" seed="7"/><feDisplacementMap in="SourceGraphic" scale="5"/></filter></defs>
        {space ? <><circle cx="250" cy="475" r="105" fill="#335e82"/><path d="M176 432q70-70 143-5t5 93q-91 40-154-8Z" fill="#78946f" opacity=".85"/><circle cx="1045" cy="215" r="92" fill="#c9c2ae"/><circle cx="1015" cy="190" r="15" fill="#9b9588"/><circle cx="1070" cy="245" r="23" fill="#9b9588"/>{Array.from({length: 26}, (_, index) => <circle key={index} cx={(index * 173) % width} cy={(index * 97) % height} r={index % 3 + 1} fill="#fff" opacity=".55"/>)}</> : <><path d="M-20 180 C180 90 310 240 430 210 C590 170 680 290 820 220 C990 120 1120 210 1310 110 L1320 650 C1090 720 900 610 710 690 C480 770 260 620 -20 720 Z" fill="#b9aa86" stroke="#6c604a" strokeWidth="4" filter="url(#rough)" /><path d="M80 520 C260 470 330 570 510 510 S820 450 1040 520" fill="none" stroke="#8ca0a0" strokeWidth="35" opacity=".6" /></>}
        {route ? <path d={pathFromRoute(route, width, height)} fill="none" stroke={colors.accent} strokeWidth="10" strokeLinecap="round" strokeDasharray="1400" strokeDashoffset={1400 * (1 - progress)} /> : null}
        {scene.payload.points.map((point, index) => <g key={point.name} opacity={interpolate(progress, [index / scene.payload.points.length, Math.min(1, index / scene.payload.points.length + .18)], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}>
          <circle cx={point.x * width} cy={point.y * height} r="14" fill={colors.accent} stroke={colors.paper} strokeWidth="5" />
          <text x={point.x * width + 22} y={point.y * height - 18} fill={space ? colors.paper : colors.ink} fontFamily="Georgia" fontWeight="bold" fontSize="30">{point.name}</text>
        </g>)}
      </svg>
      <div style={{position: 'absolute', left: 76, top: 60, color: space ? colors.paper : colors.ink}}><div style={{fontFamily: 'Arial', fontSize: 18, letterSpacing: 5, fontWeight: 800, color: colors.accent}}>{scene.payload.year}</div><div style={{fontFamily: 'Georgia', fontSize: 62, fontWeight: 700}}>{scene.payload.label}</div><div style={{fontFamily: 'Georgia', fontSize: 26, fontStyle: 'italic'}}>{scene.payload.region}</div></div>
    </AbsoluteFill>
  </FilmFrame>;
};
