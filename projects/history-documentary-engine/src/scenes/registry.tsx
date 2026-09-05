import type {ComponentType} from 'react';
import type {Scene} from '../manifest/schema';
import {ArchivePhoto} from './ArchivePhoto';
import {KenBurns} from './KenBurns';
import {MapScene} from './MapScene';
import {TitleCard} from './TitleCard';
import {DateCard, DocumentExcerpt, QuoteCard, StatisticCard} from './GraphicCards';
import {MapLibreScene} from './MapLibreScene';
import {ChapterCard, Diagram, Illustration, LabeledCutout} from './VisualExplainers';

type SceneRenderer = ComponentType<{scene: never}>;

export const sceneRegistry: Record<Scene['type'], SceneRenderer> = {
  TITLE_CARD: TitleCard as SceneRenderer,
  ARCHIVE_PHOTO: ArchivePhoto as SceneRenderer,
  DOCUMENT_EXCERPT: DocumentExcerpt as SceneRenderer,
  QUOTE_CARD: QuoteCard as SceneRenderer,
  STATISTIC: StatisticCard as SceneRenderer,
  DATE_CARD: DateCard as SceneRenderer,
  CHAPTER_CARD: ChapterCard as SceneRenderer,
  LABELED_CUTOUT: LabeledCutout as SceneRenderer,
  DIAGRAM: Diagram as SceneRenderer,
  ILLUSTRATION: Illustration as SceneRenderer,
  KEN_BURNS: KenBurns as SceneRenderer,
  MAP: MapScene as SceneRenderer,
};

export const RegisteredScene = ({scene}: {scene: Scene}) => {
  const Renderer = scene.type === 'MAP' && scene.payload.renderer === 'maplibre' ? MapLibreScene as SceneRenderer : sceneRegistry[scene.type];
  return <Renderer scene={scene as never} />;
};
