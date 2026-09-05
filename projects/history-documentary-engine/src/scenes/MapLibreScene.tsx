import {useEffect, useRef} from 'react';
import maplibregl, {type Map as MapLibreMap, type StyleSpecification} from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import {AbsoluteFill, continueRender, delayRender, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../manifest/schema';
import {colors, FilmFrame} from './shared';

type MapSceneType = Extract<Scene, {type: 'MAP'}>;
const blankStyle: StyleSpecification = {version: 8, sources: {}, layers: [{id: 'paper', type: 'background', paint: {'background-color': colors.paper}}]};

export const MapLibreScene = ({scene}: {scene: MapSceneType}) => {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const handle = useRef<number | null>(null);
  if (handle.current === null) handle.current = delayRender(`Loading MapLibre scene ${scene.id}`);
  const frame = useCurrentFrame();
  const {durationInFrames, width, height} = useVideoConfig();
  useEffect(() => {
    if (!container.current || map.current) return;
    const camera = scene.payload.camera ?? {from: [0, 10, 1.1] as [number, number, number], to: [0, 10, 1.1] as [number, number, number]};
    const instance = new maplibregl.Map({container: container.current, style: blankStyle, center: camera.from.slice(0, 2) as [number, number], zoom: camera.from[2], interactive: false, attributionControl: false, fadeDuration: 0, canvasContextAttributes: {preserveDrawingBuffer: true}});
    map.current = instance;
    instance.once('load', () => {
      instance.resize();
      if (scene.payload.geojson) {
        instance.addSource('history-data', {type: 'geojson', data: scene.payload.geojson});
        instance.addLayer({id: 'regions', type: 'fill', source: 'history-data', filter: ['==', ['geometry-type'], 'Polygon'], paint: {'fill-color': colors.accent, 'fill-opacity': .28, 'fill-outline-color': colors.accent}});
        instance.addLayer({id: 'routes', type: 'line', source: 'history-data', filter: ['==', ['geometry-type'], 'LineString'], paint: {'line-color': colors.accent, 'line-width': 6}});
        instance.addLayer({id: 'locations', type: 'circle', source: 'history-data', filter: ['==', ['geometry-type'], 'Point'], paint: {'circle-radius': 9, 'circle-color': colors.accent, 'circle-stroke-color': colors.paper, 'circle-stroke-width': 3}});
      }
      if (handle.current !== null) continueRender(handle.current);
    });
    return () => { instance.remove(); map.current = null; };
  }, [scene]);
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const camera = scene.payload.camera;
    if (!camera) return;
    const progress = interpolate(frame, [0, durationInFrames - 1], [0, 1], {extrapolateRight: 'clamp'});
    instance.jumpTo({center: [interpolate(progress, [0, 1], [camera.from[0], camera.to[0]]), interpolate(progress, [0, 1], [camera.from[1], camera.to[1]])], zoom: interpolate(progress, [0, 1], [camera.from[2], camera.to[2]])});
  }, [durationInFrames, frame, scene.payload.camera]);
  return <FilmFrame caption={scene.captions?.length ? undefined : scene.caption} credit={scene.payload.attribution ?? 'MapLibre · local GeoJSON'}>
    <AbsoluteFill><div ref={container} style={{position: 'absolute', left: 0, top: 0, width, height}} />
      <div style={{position: 'absolute', zIndex: 2, left: 70, top: 55, color: colors.ink, background: '#e7dfcbdd', padding: '22px 28px'}}>
        <div style={{font: '800 17px Arial', letterSpacing: 5, color: colors.accent}}>{scene.payload.year}</div>
        <div style={{font: '700 54px Georgia'}}>{scene.payload.label}</div>
        <div style={{font: 'italic 24px Georgia'}}>{scene.payload.region}</div>
      </div>
    </AbsoluteFill>
  </FilmFrame>;
};
