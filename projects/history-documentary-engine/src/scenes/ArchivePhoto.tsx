import {AbsoluteFill, Img, staticFile} from 'remotion';
import type {Scene} from '../manifest/schema';
import {FilmFrame, useEntrance} from './shared';

type ArchiveScene = Extract<Scene, {type: 'ARCHIVE_PHOTO'}>;
export const ArchivePhoto = ({scene}: {scene: ArchiveScene}) => {
  const entrance = useEntrance();
  return <FilmFrame caption={scene.captions?.length ? undefined : scene.caption} credit={scene.payload.credit}>
    <AbsoluteFill style={{padding: '70px 100px 120px'}}>
      <div style={{...entrance, width: '100%', height: '100%', background: '#d9cfb8', padding: 18, boxShadow: '0 20px 60px #000'}}>
        <Img src={staticFile(scene.payload.src)} alt={scene.payload.alt} style={{width: '100%', height: '100%', objectFit: 'cover', filter: 'sepia(.7) contrast(1.12) grayscale(.55)'}} />
      </div>
    </AbsoluteFill>
  </FilmFrame>;
};
