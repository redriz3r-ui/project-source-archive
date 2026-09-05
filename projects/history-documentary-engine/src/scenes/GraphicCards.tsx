import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../manifest/schema';
import {colors, FilmFrame, useEntrance} from './shared';

type DocumentScene = Extract<Scene, {type: 'DOCUMENT_EXCERPT'}>;
type QuoteScene = Extract<Scene, {type: 'QUOTE_CARD'}>;
type StatisticScene = Extract<Scene, {type: 'STATISTIC'}>;
type DateScene = Extract<Scene, {type: 'DATE_CARD'}>;

export const DocumentExcerpt = ({scene}: {scene: DocumentScene}) => <FilmFrame>
  <AbsoluteFill style={{background: '#302c24', alignItems: 'center', justifyContent: 'center'}}>
    <div style={{...useEntrance(), width: 900, minHeight: 480, boxSizing: 'border-box', padding: '60px 72px', background: colors.paper, color: colors.ink, boxShadow: '0 24px 70px #0009', transform: `${useEntrance().transform} rotate(-1deg)`}}>
      <div style={{fontFamily: 'Arial', color: colors.accent, letterSpacing: 5, fontWeight: 800, fontSize: 17}}>{scene.payload.heading.toUpperCase()}</div>
      <p style={{fontFamily: 'Georgia', fontSize: 35, lineHeight: 1.45, margin: '34px 0'}}>{scene.payload.excerpt}</p>
      <div style={{fontFamily: 'Arial', fontSize: 16, opacity: .7}}>{[scene.payload.document, scene.payload.date].filter(Boolean).join(' · ')}</div>
    </div>
  </AbsoluteFill>
</FilmFrame>;

export const QuoteCard = ({scene}: {scene: QuoteScene}) => <FilmFrame>
  <AbsoluteFill style={{background: colors.ink, alignItems: 'center', justifyContent: 'center', padding: 120, boxSizing: 'border-box'}}>
    <div style={{...useEntrance(), maxWidth: 1040, textAlign: 'center'}}>
      <div style={{fontFamily: 'Georgia', fontSize: 110, color: colors.accent, height: 80}}>“</div>
      <div style={{fontFamily: 'Georgia', fontSize: 48, lineHeight: 1.3, fontStyle: 'italic'}}>{scene.payload.quote}</div>
      <div style={{marginTop: 42, fontFamily: 'Arial', fontSize: 18, letterSpacing: 4, color: colors.accent}}>{scene.payload.attribution.toUpperCase()}{scene.payload.date ? ` · ${scene.payload.date}` : ''}</div>
    </div>
  </AbsoluteFill>
</FilmFrame>;

export const StatisticCard = ({scene}: {scene: StatisticScene}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const scale = interpolate(frame, [0, 18, durationInFrames], [.8, 1, 1.04], {extrapolateRight: 'clamp'});
  return <FilmFrame><AbsoluteFill style={{background: colors.paper, color: colors.ink, justifyContent: 'center', padding: 110, boxSizing: 'border-box'}}>
    <div style={{fontFamily: 'Arial', color: colors.accent, letterSpacing: 7, fontWeight: 900}}>BY THE NUMBERS</div>
    <div style={{fontFamily: 'Georgia', fontSize: 170, fontWeight: 800, letterSpacing: -8, transform: `scale(${scale})`, transformOrigin: 'left center'}}>{scene.payload.value}</div>
    <div style={{fontFamily: 'Georgia', fontSize: 35, lineHeight: 1.35, maxWidth: 1000}}>{scene.payload.label}</div>
  </AbsoluteFill></FilmFrame>;
};

export const DateCard = ({scene}: {scene: DateScene}) => <FilmFrame>
  <AbsoluteFill style={{background: colors.ink, justifyContent: 'center', padding: 105, boxSizing: 'border-box'}}>
    <div style={{...useEntrance()}}><div style={{fontFamily: 'Georgia', color: colors.accent, fontSize: 155, lineHeight: 1, fontWeight: 800}}>{scene.payload.date}</div>
    <div style={{width: 180, borderTop: `6px solid ${colors.paper}`, margin: '34px 0'}} />
    <div style={{fontFamily: 'Georgia', fontSize: 43, lineHeight: 1.3, maxWidth: 1000}}>{scene.payload.headline}</div></div>
  </AbsoluteFill>
</FilmFrame>;
