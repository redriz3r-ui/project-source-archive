import React from 'react';
import {AbsoluteFill, Audio, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {presidentGridEntries, type PresidentGridEntry} from './presidents';

const columns = 5;
const cardWidth = 330;
const cardHeight = 245;
const gap = 24;
const boardWidth = columns * cardWidth + (columns - 1) * gap;
const boardHeight = 4 * cardHeight + 3 * gap;

const positionFor = (index: number) => {
  const row = Math.floor(index / columns);
  const itemsInRow = row === 3 ? 2 : columns;
  const rowWidth = itemsInRow * cardWidth + (itemsInRow - 1) * gap;
  const rowStart = (boardWidth - rowWidth) / 2;
  const column = row === 3 ? index - 15 : index % columns;
  return {x: rowStart + column * (cardWidth + gap), y: row * (cardHeight + gap)};
};

const smooth = (value: number) => value * value * (3 - 2 * value);

const cameraTarget = (focusIndex: number) => {
  const {x, y} = positionFor(focusIndex);
  const targetX = boardWidth / 2 - (x + cardWidth / 2);
  const targetY = boardHeight / 2 - (y + cardHeight / 2);
  return {x: targetX, y: targetY};
};

const GridCard: React.FC<{entry: PresidentGridEntry; index: number; active: boolean; emphasis: number}> = ({entry, index, active, emphasis}) => {
  const {x, y} = positionFor(index);
  return <div style={{
    position: 'absolute', left: x, top: y, width: cardWidth, height: cardHeight,
    overflow: 'hidden', borderRadius: 7,
    border: `${active ? 5 : 2}px solid ${active ? '#f3c95d' : 'rgba(255,255,255,.18)'}`,
    background: '#101216', color: '#fff', boxShadow: active ? `0 0 ${38 * emphasis}px rgba(190,137,20,.5)` : '0 10px 28px rgba(21,25,32,.2)',
    filter: active ? 'none' : 'saturate(.72) brightness(.78)',
  }}>
    <img src={staticFile(entry.portraitSrc)} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center 22%'}} />
    <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(180deg,transparent 43%,rgba(4,6,10,.94) 100%)'}} />
    <div style={{position: 'absolute', left: 17, top: 14, width: 37, height: 37, borderRadius: 99, background: active ? '#f3c95d' : 'rgba(5,7,10,.82)', color: active ? '#16120a' : '#fff', display: 'grid', placeItems: 'center', fontSize: 20, fontWeight: 900}}>{entry.number}</div>
    <div style={{position: 'absolute', left: 17, right: 14, bottom: 15}}>
      <div style={{fontSize: 25, lineHeight: 1, fontWeight: 900, letterSpacing: -.5}}>{entry.name}</div>
      <div style={{fontSize: 15, color: active ? '#f3c95d' : '#c9cbd0', marginTop: 7, fontWeight: 700, letterSpacing: 1}}>{entry.term}</div>
    </div>
  </div>;
};

const GridStage: React.FC<{activeIndex: number; scale: number; x: number; y: number; emphasis: number; titleOpacity?: number}> = ({activeIndex, scale, x, y, emphasis, titleOpacity = 0}) => {
  const {width, height} = useVideoConfig();
  const baseScale = Math.min((width - 100) / boardWidth, (height - 150) / boardHeight);
  return <AbsoluteFill style={{background: '#f7f6f2', color: '#15171b', fontFamily: 'Arial, Helvetica, sans-serif', overflow: 'hidden'}}>
    <Audio src={staticFile('projects/episode-2/audio/score.wav')} volume={0} />
    <AbsoluteFill style={{background: 'radial-gradient(circle at 50% 42%,#ffffff 0%,#f5f3ed 60%,#ece9e1 100%)'}} />
    <div style={{position: 'absolute', left: '50%', top: '50%', width: boardWidth, height: boardHeight, transformOrigin: 'center center', transform: `translate(-50%,-50%) scale(${baseScale * scale}) translate(${x}px,${y}px)`}}>
      {presidentGridEntries.map((entry, index) => <GridCard key={entry.number} entry={entry} index={index} active={index === activeIndex} emphasis={emphasis} />)}
    </div>
    <div style={{position: 'absolute', left: 0, right: 0, top: 22, textAlign: 'center', opacity: titleOpacity}}>
      <div style={{fontSize: 37, fontWeight: 950, letterSpacing: -1.5, color: '#15171b'}}>EVERY PHILIPPINE PRESIDENT EXPLAINED</div>
    </div>
  </AbsoluteFill>;
};

export type PresidentGridChapterTransitionProps = {
  mode: 'INTRO' | 'MOVE' | 'OUTRO';
  fromIndex: number;
  toIndex: number;
  announcementSrc?: string;
};

export const PresidentGridChapterTransition: React.FC<PresidentGridChapterTransitionProps> = ({mode, fromIndex, toIndex, announcementSrc}) => {
  const frame = useCurrentFrame();
  const from = cameraTarget(fromIndex);
  const to = cameraTarget(toIndex);
  if (mode === 'INTRO') {
    const enter = smooth(interpolate(frame, [28, 76], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
    return <><GridStage activeIndex={toIndex} scale={1 + 1.9 * enter} x={to.x * enter} y={to.y * enter} emphasis={enter} titleOpacity={1 - enter} />{announcementSrc && <Audio src={staticFile(announcementSrc)} />}</>;
  }
  if (mode === 'OUTRO') {
    const exit = smooth(interpolate(frame, [12, 66], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
    return <GridStage activeIndex={fromIndex} scale={2.9 - 1.9 * exit} x={from.x * (1 - exit)} y={from.y * (1 - exit)} emphasis={1 - exit} titleOpacity={exit} />;
  }
  const move = smooth(interpolate(frame, [12, 62], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  return <><GridStage activeIndex={move < .5 ? fromIndex : toIndex} scale={2.9} x={interpolate(move, [0, 1], [from.x, to.x])} y={interpolate(move, [0, 1], [from.y, to.y])} emphasis={1} />{announcementSrc && <Audio src={staticFile(announcementSrc)} />}</>;
};

export const PresidentGridTransition: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const enter = smooth(interpolate(frame, [75, 125], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  const move = smooth(interpolate(frame, [170, 225], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  const activeIndex = move < .5 ? 0 : 1;
  const firstTarget = cameraTarget(0);
  const secondTarget = cameraTarget(1);
  const camera = {
    scale: 1 + (2.9 - 1) * enter,
    x: enter * interpolate(move, [0, 1], [firstTarget.x, secondTarget.x]),
    y: enter * interpolate(move, [0, 1], [firstTarget.y, secondTarget.y]),
    enter,
  };
  const baseScale = Math.min((width - 100) / boardWidth, (height - 150) / boardHeight);
  const intro = spring({frame, fps, config: {damping: 18, stiffness: 90}});
  const chapterOpacity = interpolate(camera.enter, [.72, 1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  return <AbsoluteFill style={{background: '#f7f6f2', color: '#15171b', fontFamily: 'Arial, Helvetica, sans-serif', overflow: 'hidden'}}>
    <AbsoluteFill style={{background: 'radial-gradient(circle at 50% 42%,#ffffff 0%,#f5f3ed 60%,#ece9e1 100%)'}} />
    <div style={{position: 'absolute', left: '50%', top: '50%', width: boardWidth, height: boardHeight, transformOrigin: 'center center', transform: `translate(-50%,-50%) scale(${baseScale * camera.scale * (.96 + intro * .04)}) translate(${camera.x}px,${camera.y}px)`}}>
      {presidentGridEntries.map((entry, index) => <GridCard key={entry.number} entry={entry} index={index} active={index === activeIndex} emphasis={camera.enter} />)}
    </div>
    <div style={{position: 'absolute', left: 0, right: 0, top: 22, textAlign: 'center', opacity: 1 - chapterOpacity}}>
      <div style={{fontSize: 37, fontWeight: 950, letterSpacing: -1.5, color: '#15171b'}}>EVERY PHILIPPINE PRESIDENT EXPLAINED</div>
    </div>
  </AbsoluteFill>;
};
