import {useCurrentFrame} from 'remotion';
import type {Scene} from '../manifest/schema';

export const CaptionOverlay = ({scene}: {scene: Scene}) => {
  const frame = useCurrentFrame();
  const caption = scene.captions?.find((item) => frame >= item.startFrame && frame < item.endFrame);
  if (!caption) return null;
  return <div style={{
    position: 'absolute', left: 110, right: 110, bottom: 48, display: 'flex', justifyContent: 'center',
    fontFamily: 'Arial, Helvetica, sans-serif', fontSize: 34, fontWeight: 700, lineHeight: 1.25,
    textAlign: 'center', color: '#f4efdf', textShadow: '0 3px 12px #000, 0 1px 2px #000', zIndex: 20,
  }}>
    <span style={{background: 'rgba(12, 12, 10, .76)', padding: '12px 20px 14px', borderRadius: 4}}>{caption.text}</span>
  </div>;
};
