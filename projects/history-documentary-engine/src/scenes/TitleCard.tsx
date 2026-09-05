import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../manifest/schema';
import {colors} from './shared';

type TitleScene = Extract<Scene, {type: 'TITLE_CARD'}>;
export const TitleCard = ({scene}: {scene: TitleScene}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const scale = interpolate(frame, [0, durationInFrames], [1.04, 1.1]);
  const hasArchive = Boolean(scene.payload.backgroundSrc);
  return <AbsoluteFill style={{background: colors.ink, color: '#fff', justifyContent: 'center', padding: 76, overflow: 'hidden'}}>
    {scene.payload.backgroundSrc ? <AbsoluteFill style={{transform:`scale(${scale})`}}><Img src={staticFile(scene.payload.backgroundSrc)} alt={scene.payload.backgroundAlt ?? ''} style={{width:'100%',height:'100%',objectFit:'cover',filter:'contrast(1.08) saturate(.82) brightness(.55)'}} /></AbsoluteFill> : null}
    <AbsoluteFill style={{background:'linear-gradient(90deg, rgba(0,0,0,.82), rgba(0,0,0,.4) 68%, rgba(0,0,0,.2))'}} />
    <div style={{position:'relative',maxWidth:900}}>
      <div style={{fontFamily:'Arial, sans-serif',color:'#ddd',fontWeight:800,letterSpacing:7,fontSize:18,marginBottom:24}}>{scene.payload.eyebrow ?? 'A SHORT HISTORY'}</div>
      <h1 style={{fontFamily:'Georgia, serif',fontSize:76,lineHeight:1,maxWidth:850,margin:0,letterSpacing:-2}}>{scene.payload.title}</h1>
      {scene.payload.subtitle ? <p style={{fontFamily:'Georgia, serif',fontStyle:'italic',fontSize:25,maxWidth:760,lineHeight:1.3,marginTop:26,color:'#e8e8e8'}}>{scene.payload.subtitle}</p> : null}
    </div>
    {hasArchive && scene.payload.backgroundCredit ? <div style={{position:'absolute',right:28,top:24,fontFamily:'Arial, sans-serif',fontSize:12,letterSpacing:1.2,opacity:.72}}>{scene.payload.backgroundCredit.toUpperCase()}</div> : null}
  </AbsoluteFill>;
};
