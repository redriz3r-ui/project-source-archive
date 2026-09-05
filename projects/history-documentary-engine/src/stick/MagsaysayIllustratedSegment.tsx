import { Audio } from "@remotion/media";
import {
  AbsoluteFill,
  Img,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { PresidentSegment } from "../presidents/schema";
import {
  BallotBox,
  Citizen,
  Gate,
  LetterPile,
  Magsaysay,
  Plane,
  TrustMeter,
} from "./library/MagsaysayKit";
import {
  VisualSceneLayout,
  type VisualSceneLayoutName,
} from "./layouts/VisualSceneLayout";

const marker = "Comic Sans MS, Marker Felt, sans-serif";
const cue: {
  pose: Parameters<typeof Magsaysay>[0]["pose"];
  outfit: Parameters<typeof Magsaysay>[0]["outfit"];
  label: string;
}[] = [
  { pose: "neutral", outfit: "barong", label: "THE PEOPLE TRUSTED HIM" },
  { pose: "mechanic", outfit: "mechanic", label: "MECHANIC → GUERRILLA" },
  { pose: "salute", outfit: "suit", label: "DEFENSE SECRETARY" },
  { pose: "point", outfit: "barong", label: "A LANDSLIDE" },
  { pose: "welcome", outfit: "barong", label: "THE GATES OPEN" },
  { pose: "listen", outfit: "barong", label: "60,000 COMPLAINTS" },
  { pose: "welcome", outfit: "barong", label: "TRUST RESTORED" },
  { pose: "worried", outfit: "suit", label: "COLD WAR ALLIANCE" },
  { pose: "sad", outfit: "suit", label: "CEBU · 1957" },
];
const layouts: VisualSceneLayoutName[] = [
  "HERO_CENTER",
  "EVIDENCE_LEFT",
  "EVIDENCE_RIGHT",
  "TWO_SIDED_CONTEXT",
  "ENVIRONMENT_SCENE",
  "EVIDENCE_LEFT",
  "HERO_CENTER",
  "EVIDENCE_RIGHT",
  "EVIDENCE_TAKEOVER",
];
const beatAssets = (
  beat: PresidentSegment["beats"][number],
  manifest: PresidentSegment,
) =>
  beat.assetIds
    .map((id) => manifest.assets.find((a) => a.id === id))
    .filter(Boolean) as PresidentSegment["assets"];
const Art = ({ index, progress }: { index: number; progress: number }) => (
  <svg viewBox="0 0 620 720" width="100%" height="100%">
    {index === 0 && <Magsaysay x={315} y={550} scale={1.55} pose="neutral" />}
    {index === 1 && (
      <>
        <Magsaysay
          x={280}
          y={500}
          scale={1.35}
          pose="mechanic"
          outfit="mechanic"
        />
        <Citizen x={470} y={510} hat color="#537f42" />
        <text
          x="400"
          y="160"
          fontFamily={marker}
          fontSize="43"
          fontWeight="900"
        >
          10,000
        </text>
      </>
    )}
    {index === 2 && (
      <>
        <Magsaysay x={310} y={505} scale={1.55} pose="salute" outfit="suit" />
        <text
          x="310"
          y="160"
          textAnchor="middle"
          fontFamily={marker}
          fontWeight="900"
          fontSize="32"
        >
          CONGRESS → DEFENSE
        </text>
      </>
    )}
    {index === 3 && (
      <>
        <Magsaysay x={220} y={505} scale={1.25} pose="point" />
        <BallotBox x={450} y={430} />
        <text
          x="430"
          y="220"
          textAnchor="middle"
          fontFamily={marker}
          fill="#d8322a"
          fontWeight="900"
          fontSize="50"
        >
          WIN!
        </text>
      </>
    )}
    {index === 4 && (
      <>
        <Gate x={310} y={440} open={progress} />
        <Magsaysay x={310} y={570} pose="welcome" scale={0.82} />
        <Citizen x={75 + progress * 120} y={600} scale={0.65} />
        <Citizen
          x={150 + progress * 120}
          y={610}
          color="#3e78a1"
          scale={0.58}
        />
      </>
    )}
    {index === 5 && (
      <>
        <Magsaysay x={170} y={540} pose="listen" />
        <LetterPile x={430} y={340} />
        <text
          x="420"
          y="510"
          textAnchor="middle"
          fontFamily={marker}
          fill="#d8322a"
          fontWeight="900"
          fontSize="34"
        >
          30,000 SETTLED
        </text>
      </>
    )}
    {index === 6 && (
      <>
        <Magsaysay x={310} y={545} pose="welcome" scale={1.15} />
        <TrustMeter x={310} y={112} value={progress} />
      </>
    )}
    {index === 7 && (
      <>
        <Magsaysay x={310} y={545} pose="worried" outfit="suit" />
        <g fontFamily={marker} fontWeight="900" fontSize="25">
          <text x="65" y="210">
            SEATO
          </text>
          <text x="398" y="210">
            U.S. ALLIANCE
          </text>
        </g>
        <path d="M135 230 H485" stroke="#d8322a" strokeWidth="8" />
      </>
    )}
    {index === 8 && (
      <>
        <Plane
          x={300 - progress * 180}
          y={190 + progress * 145}
          rotate={progress * 22}
        />
        <path d="M60 600 Q220 370 360 600 T610 600" fill="#777" opacity=".7" />
        <Magsaysay x={480} y={575} pose="sad" scale={0.78} />
      </>
    )}
  </svg>
);
const Beat = ({
  beat,
  manifest,
  index,
}: {
  beat: PresidentSegment["beats"][number];
  manifest: PresidentSegment;
  index: number;
}) => {
  const frame = useCurrentFrame(),
    { durationInFrames } = useVideoConfig(),
    progress = interpolate(frame, [0, durationInFrames], [0, 1], {
      extrapolateRight: "clamp",
    }),
    assets = beatAssets(beat, manifest),
    asset =
      assets[Math.min(assets.length - 1, Math.floor(progress * assets.length))];
  return (
    <AbsoluteFill
      style={{ background: "#fff", fontFamily: "Arial", overflow: "hidden" }}
    >
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 18,
          textAlign: "center",
          fontFamily: marker,
          fontWeight: 900,
          zIndex: 10,
          background: "#fff",
        }}
      >
        <div style={{ fontSize: 54, lineHeight: 1.05 }}>RAMON MAGSAYSAY</div>
        <div style={{ fontSize: 27, lineHeight: 1.35 }}>(1953 to 1957)</div>
      </div>
      {index === 0 ? (
        <div
          style={{
            position: "absolute",
            left: 330,
            top: 45,
            width: 620,
            height: 675,
          }}
        >
          <Art index={index} progress={progress} />
        </div>
      ) : (
        <VisualSceneLayout
          layout={layouts[index]}
          progress={progress}
          photo={
            asset && (
              <Img
                src={staticFile(asset.src)}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "contain",
                  background: "#eee",
                }}
              />
            )
          }
          art={<Art index={index} progress={progress} />}
        />
      )}
      {index !== 0 && (
        <div
          style={{
            position: "absolute",
            right: 35,
            bottom: 30,
            width: 550,
            textAlign: "center",
            fontFamily: marker,
            fontSize: 31,
            fontWeight: 900,
            color: index === 8 ? "#b52c24" : "#111",
          }}
        >
          {cue[index].label}
        </div>
      )}
      {index !== 0 && (
        <div
          style={{
            position: "absolute",
            left: 32,
            bottom: 18,
            fontSize: 9,
            color: "#555",
          }}
        >
          {asset?.source} · {asset?.rightsText}
        </div>
      )}
    </AbsoluteFill>
  );
};
export const MagsaysayIllustratedSegment = ({
  manifest,
}: {
  manifest: PresidentSegment;
}) => {
  let cursor = 0;
  return (
    <AbsoluteFill style={{ background: "#fff" }}>
      <Audio src={staticFile(manifest.soundtrackSrc)} volume={0.025} loop />
      {manifest.beats.map((beat, index) => {
        const from = cursor,
          duration = Math.ceil(beat.durationSeconds * manifest.fps);
        cursor += duration;
        return (
          <Sequence key={beat.id} from={from} durationInFrames={duration}>
            <Beat beat={beat} manifest={manifest} index={index} />
            <Audio src={staticFile(beat.audioSrc)} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
