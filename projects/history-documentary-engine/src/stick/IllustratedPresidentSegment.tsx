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
  VisualSceneLayout,
  type VisualSceneLayoutName,
} from "./layouts/VisualSceneLayout";
import { PresidentFigure, type FigurePose } from "./library/PresidentFigure";
import {
  presidentProfileOrder,
  presidentProfiles,
} from "./library/PresidentProfiles";
import {
  BallotBox,
  Citizen,
  Gate,
  LetterPile,
  TrustMeter,
} from "./library/MagsaysayKit";

const marker = "Comic Sans MS, Marker Felt, sans-serif";
const purposeLabel: Record<string, string> = {
  HOOK: "WHO WERE THEY?",
  RISE: "THE RISE",
  INDEPENDENCE: "INDEPENDENCE",
  ACHIEVEMENT: "WHAT CHANGED",
  REVERSAL: "A REVERSAL",
  ESCALATION: "PRESSURE RISES",
  CONTROVERSY: "THE CONTROVERSY",
  FALL: "THE FALL",
  RETURN: "THE RETURN",
  LEGACY_HANDOFF: "THE LEGACY",
  ELECTION: "THE ELECTION",
  CHALLENGE: "THE CHALLENGE",
  POLICY: "THE POLICY",
  REFORMS: "REFORMS",
  WAR: "WAR",
  EXILE: "EXILE",
  DEATH_LEGACY: "THE LEGACY",
  HANDOFF: "WHAT CAME NEXT",
};
const layoutFor = (purpose: string, index: number): VisualSceneLayoutName => {
  if (index === 0) return "HERO_CENTER";
  if (["FALL", "DEATH_LEGACY", "REVERSAL"].includes(purpose))
    return "EVIDENCE_TAKEOVER";
  if (["WAR", "EXILE", "ESCALATION"].includes(purpose))
    return "ENVIRONMENT_SCENE";
  if (["CONTROVERSY", "CHALLENGE"].includes(purpose))
    return "TWO_SIDED_CONTEXT";
  if (index % 5 === 0) return "HERO_CENTER";
  return index % 2 === 0 ? "EVIDENCE_RIGHT" : "EVIDENCE_LEFT";
};
const poseFor = (purpose: string): FigurePose =>
  purpose === "FALL" || purpose === "DEATH_LEGACY"
    ? "sad"
    : purpose === "CONTROVERSY" || purpose === "CHALLENGE"
      ? "worried"
      : purpose === "ELECTION" || purpose === "ACHIEVEMENT"
        ? "welcome"
        : purpose === "WAR"
          ? "salute"
          : purpose === "POLICY" || purpose === "REFORMS"
            ? "point"
            : "neutral";

const BeatArt = ({
  manifest,
  index,
  progress,
}: {
  manifest: PresidentSegment;
  index: number;
  progress: number;
}) => {
  const beat = manifest.beats[index],
    profile =
      presidentProfiles[presidentProfileOrder[manifest.presidentNumber - 1]],
    purpose = beat.purpose,
    pose = poseFor(purpose);
  return (
    <svg viewBox="0 0 620 720" width="100%" height="100%">
      <PresidentFigure
        profile={profile}
        x={purpose === "ELECTION" ? 210 : 310}
        y={545}
        scale={index === 0 ? 1.55 : 1.15}
        pose={pose}
      />
      {index > 0 && purpose === "ELECTION" && <BallotBox x={455} y={450} />}
      {index > 0 && ["POLICY", "REFORMS"].includes(purpose) && (
        <>
          <LetterPile x={455} y={350} />
          <Gate x={455} y={520} open={progress} />
        </>
      )}
      {index > 0 && purpose === "ACHIEVEMENT" && (
        <TrustMeter x={310} y={125} value={Math.max(0.15, progress)} />
      )}
      {index > 0 && ["WAR", "ESCALATION"].includes(purpose) && (
        <>
          <Citizen x={455} y={550} color="#667a55" hat />
          <path
            d="M100 205 H520"
            stroke="#d8322a"
            strokeWidth="9"
            strokeDasharray="18 13"
          />
        </>
      )}
      {index > 0 &&
        ["CONTROVERSY", "CHALLENGE", "REVERSAL"].includes(purpose) && (
          <>
            <path d="M95 220 H525" stroke="#d8322a" strokeWidth="9" />
            <text
              x="310"
              y="195"
              textAnchor="middle"
              fontFamily={marker}
              fontWeight="900"
              fontSize="34"
            >
              PRESSURE
            </text>
          </>
        )}
      {index > 0 && ["FALL", "DEATH_LEGACY", "EXILE"].includes(purpose) && (
        <path d="M75 580 Q210 390 330 580 T600 580" fill="#999" opacity=".65" />
      )}
    </svg>
  );
};

const Beat = ({
  manifest,
  index,
}: {
  manifest: PresidentSegment;
  index: number;
}) => {
  const beat = manifest.beats[index],
    frame = useCurrentFrame(),
    { durationInFrames } = useVideoConfig(),
    progress = interpolate(frame, [0, durationInFrames], [0, 1], {
      extrapolateRight: "clamp",
    }),
    assets = beat.assetIds
      .map((id) => manifest.assets.find((a) => a.id === id))
      .filter(Boolean) as PresidentSegment["assets"],
    asset =
      assets[Math.min(assets.length - 1, Math.floor(progress * assets.length))];
  const art = <BeatArt manifest={manifest} index={index} progress={progress} />;
  return (
    <AbsoluteFill style={{ background: "#fff", overflow: "hidden" }}>
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
        <div
          style={{
            fontSize: manifest.presidentName.length > 22 ? 43 : 54,
            lineHeight: 1.05,
            textTransform: "uppercase",
          }}
        >
          {manifest.presidentName}
        </div>
        <div style={{ fontSize: 27, lineHeight: 1.35 }}>
          ({manifest.term.replace("–", " to ")})
        </div>
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
          {art}
        </div>
      ) : (
        <VisualSceneLayout
          layout={layoutFor(beat.purpose, index)}
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
          art={art}
        />
      )}
      {index > 0 && (
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
            color: ["FALL", "DEATH_LEGACY"].includes(beat.purpose)
              ? "#b52c24"
              : "#111",
          }}
        >
          {purposeLabel[beat.purpose]}
        </div>
      )}
      {index > 0 && (
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

export const IllustratedPresidentSegment = ({
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
            <Beat manifest={manifest} index={index} />
            <Audio src={staticFile(beat.audioSrc)} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
