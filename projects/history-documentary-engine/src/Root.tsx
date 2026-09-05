import { Composition } from "remotion";
import { Documentary } from "./Documentary";
import { getDurationInFrames, parseManifest } from "./manifest/schema";
import { sampleManifest } from "./manifest/sample";
import { ApolloOpening } from "./prototypes/ApolloOpening";
import { PhoneFastDocumentary } from "./phone/PhoneFast";
import { compilePhoneFast } from "./phone/compiler";
import { jordanPhoneProof } from "./phone/jordanProof";
import { manilaOpening } from "./episodes/manilaOpening";
import { manilaFull } from "./episodes/manilaFull";
import { manila1898Proof } from "./episodes/manila1898Proof";
import { WikiLearningVideo, wikiDuration } from "./wiki/WikiLearningVideo";
import wikiFullManifest from "../public/wiki-tests/battle-of-manila-1898/full-manifest.json";
import { PresidentSegment } from "./presidents/PresidentSegment";
import { presidentDuration, presidentSegmentSchema } from "./presidents/schema";
import aguinaldoManifestJson from "../public/wiki-tests/emilio-aguinaldo/president-manifest.json";
import {
  PresidentGridChapterTransition,
  PresidentGridTransition,
} from "./master/PresidentGridTransition";
import { StickFigureScene } from "./stick/StickFigureScene";
import { magsaysayStickProof } from "./stick/magsaysayProof";
import { PhotoPoseScene } from "./stick/PhotoPoseScene";
import magsaysayGuerrillaPoses from "../public/wiki-tests/ramon-magsaysay/pose-tests/wartime-guerrillas/poses.json";
import magsaysayManifestJson from "../public/wiki-tests/ramon-magsaysay/president-manifest.json";
import { MagsaysayIllustratedSegment } from "./stick/MagsaysayIllustratedSegment";
import { IllustratedPresidentSegment } from "./stick/IllustratedPresidentSegment";
import { illustratedPresidentManifests } from "./stick/presidentManifests";

const aguinaldoManifest = presidentSegmentSchema.parse(aguinaldoManifestJson);
const magsaysayManifest = presidentSegmentSchema.parse(magsaysayManifestJson);

export const RemotionRoot = () => (
  <>
    <Composition
      id="HistoryDocumentary"
      component={Documentary}
      durationInFrames={getDurationInFrames(sampleManifest)}
      fps={sampleManifest.format.fps}
      width={sampleManifest.format.width}
      height={sampleManifest.format.height}
      defaultProps={{ manifest: sampleManifest }}
      calculateMetadata={({ props }) => {
        const manifest = parseManifest(props.manifest);
        return {
          durationInFrames: getDurationInFrames(manifest),
          fps: manifest.format.fps,
          width: manifest.format.width,
          height: manifest.format.height,
          props: { manifest },
        };
      }}
    />
    <Composition
      id="ApolloOpeningArchive"
      component={ApolloOpening}
      durationInFrames={900}
      fps={30}
      width={1280}
      height={720}
    />
    <Composition
      id="JordanPhoneProof"
      component={PhoneFastDocumentary}
      durationInFrames={compilePhoneFast(jordanPhoneProof).durationInFrames}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{ blueprint: jordanPhoneProof }}
    />
    <Composition
      id="ManilaOpeningProof"
      component={PhoneFastDocumentary}
      durationInFrames={compilePhoneFast(manilaOpening).durationInFrames}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{ blueprint: manilaOpening }}
    />
    <Composition
      id="ManilaFull"
      component={PhoneFastDocumentary}
      durationInFrames={compilePhoneFast(manilaFull).durationInFrames}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{ blueprint: manilaFull }}
    />
    <Composition
      id="Manila1898WikipediaProof"
      component={PhoneFastDocumentary}
      durationInFrames={compilePhoneFast(manila1898Proof).durationInFrames}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{ blueprint: manila1898Proof }}
    />
    <Composition
      id="Manila1898WikipediaFull"
      component={WikiLearningVideo}
      durationInFrames={Math.max(1, wikiDuration(wikiFullManifest))}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{ manifest: wikiFullManifest }}
    />
    <Composition
      id="PresidentSegment"
      component={PresidentSegment}
      durationInFrames={presidentDuration(aguinaldoManifest)}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{ manifest: aguinaldoManifest }}
      calculateMetadata={({ props }) => {
        const manifest = presidentSegmentSchema.parse(props.manifest);
        return {
          durationInFrames: presidentDuration(manifest),
          fps: manifest.fps,
          width: 1280,
          height: 720,
          props: { manifest },
        };
      }}
    />
    <Composition
      id="PresidentGridTransitionProof"
      component={PresidentGridTransition}
      durationInFrames={360}
      fps={30}
      width={1280}
      height={720}
    />
    <Composition
      id="PresidentGridChapterTransition"
      component={PresidentGridChapterTransition}
      durationInFrames={90}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{
        mode: "MOVE",
        fromIndex: 0,
        toIndex: 1,
        announcementSrc: "master/audio/president-02.wav",
      }}
    />
    <Composition
      id="MagsaysayStickFigureProof"
      component={StickFigureScene}
      durationInFrames={180}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{ proof: magsaysayStickProof }}
    />
    <Composition
      id="MagsaysayPhotoPoseProof"
      component={PhotoPoseScene}
      durationInFrames={225}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{ poseData: magsaysayGuerrillaPoses }}
    />
    <Composition
      id="MagsaysayIllustratedSegment"
      component={MagsaysayIllustratedSegment}
      durationInFrames={presidentDuration(magsaysayManifest)}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{ manifest: magsaysayManifest }}
    />
    {illustratedPresidentManifests.map((manifest) => (
      <Composition
        key={manifest.presidentNumber}
        id={`IllustratedPresident${String(manifest.presidentNumber).padStart(2, "0")}`}
        component={IllustratedPresidentSegment}
        durationInFrames={presidentDuration(manifest)}
        fps={manifest.fps}
        width={1280}
        height={720}
        defaultProps={{ manifest }}
      />
    ))}
  </>
);
