import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {ReactNode} from 'react';
import type {Scene} from '../manifest/schema';
import {colors, FilmFrame, useEntrance} from './shared';

type Chapter = Extract<Scene, {type: 'CHAPTER_CARD'}>;
type Cutout = Extract<Scene, {type: 'LABELED_CUTOUT'}>;
type DiagramScene = Extract<Scene, {type: 'DIAGRAM'}>;
type IllustrationScene = Extract<Scene, {type: 'ILLUSTRATION'}>;

export const ChapterCard = ({scene}: {scene: Chapter}) => <FilmFrame>
  <AbsoluteFill style={{background: colors.paper, color: colors.ink, padding: 90, boxSizing: 'border-box', justifyContent: 'center'}}>
    <div style={{...useEntrance(), display: 'flex', alignItems: 'center', gap: 44}}>
      <div style={{fontFamily: 'Arial', fontWeight: 900, fontSize: 160, color: colors.accent, lineHeight: 1}}>{String(scene.payload.index).padStart(2, '0')}</div>
      <div><div style={{fontFamily: 'Arial', letterSpacing: 6, fontSize: 17, fontWeight: 800, opacity: .65}}>{scene.payload.kicker?.toUpperCase()}</div>
      <div style={{fontFamily: 'Georgia', fontWeight: 800, fontSize: 72, lineHeight: 1.04, maxWidth: 840}}>{scene.payload.title}</div></div>
    </div>
  </AbsoluteFill>
</FilmFrame>;

const EditorialImage = ({src, alt, children}: {src: string; alt: string; children?: ReactNode}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const scale = interpolate(frame, [0, durationInFrames], [1.02, 1.09]);
  return <AbsoluteFill style={{background: '#cfc3aa'}}>
    <Img src={staticFile(src)} alt={alt} style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${scale})`, filter: 'saturate(.82) contrast(1.08)'}} />
    <AbsoluteFill style={{background: 'linear-gradient(90deg, #111b 0%, transparent 60%), linear-gradient(0deg, #1119 0%, transparent 45%)'}} />
    {children}
  </AbsoluteFill>;
};

export const LabeledCutout = ({scene}: {scene: Cutout}) => <FilmFrame credit={scene.payload.credit}>
  <EditorialImage src={scene.payload.src} alt={scene.payload.alt}>
    <div style={{position: 'absolute', left: 70, bottom: 125, maxWidth: 760, ...useEntrance()}}>
      <div style={{display: 'inline-block', background: colors.accent, color: 'white', padding: '9px 16px', fontFamily: 'Arial', fontWeight: 900, fontSize: 22, letterSpacing: 2}}>{scene.payload.label.toUpperCase()}</div>
      {scene.payload.detail ? <div style={{marginTop: 14, fontFamily: 'Georgia', fontSize: 40, lineHeight: 1.14, fontWeight: 700}}>{scene.payload.detail}</div> : null}
    </div>
  </EditorialImage>
</FilmFrame>;

export const Illustration = ({scene}: {scene: IllustrationScene}) => <FilmFrame credit={scene.payload.credit}>
  <EditorialImage src={scene.payload.src} alt={scene.payload.alt} />
</FilmFrame>;

export const Diagram = ({scene}: {scene: DiagramScene}) => {
  const frame = useCurrentFrame();
  return <FilmFrame><AbsoluteFill style={{background: colors.paper, color: colors.ink, padding: 70, boxSizing: 'border-box'}}>
    <div style={{fontFamily: 'Arial', fontWeight: 900, letterSpacing: 5, color: colors.accent, fontSize: 18}}>{scene.payload.title.toUpperCase()}</div>
    <div style={{display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', gap: 24}}>
      {scene.payload.nodes.map((node, index) => <div key={`${node.label}-${index}`} style={{display: 'contents'}}>
        {index ? <div style={{fontFamily: 'Arial', fontSize: 28, fontWeight: 900, color: colors.accent, opacity: interpolate(frame, [index * 10, index * 10 + 8], [0, 1], {extrapolateRight: 'clamp'})}}>→</div> : null}
        <div style={{width: 300, minHeight: 190, boxSizing: 'border-box', padding: 28, background: index % 2 ? colors.ink : '#fff9', color: index % 2 ? colors.paper : colors.ink, border: `4px solid ${colors.ink}`, boxShadow: '10px 10px 0 #9f382d55', opacity: interpolate(frame, [index * 10, index * 10 + 10], [0, 1], {extrapolateRight: 'clamp'}), transform: `translateY(${interpolate(frame, [index * 10, index * 10 + 10], [25, 0], {extrapolateRight: 'clamp'})}px)`}}>
          <div style={{fontFamily: 'Georgia', fontWeight: 800, fontSize: 29, lineHeight: 1.16}}>{node.label}</div>
          {node.detail ? <div style={{fontFamily: 'Arial', marginTop: 13, fontSize: 17}}>{node.detail}</div> : null}
        </div>
      </div>)}
    </div>
    {scene.payload.relation ? <div style={{fontFamily: 'Arial', fontWeight: 900, letterSpacing: 6, textAlign: 'center', opacity: .55}}>{scene.payload.relation}</div> : null}
  </AbsoluteFill></FilmFrame>;
};
