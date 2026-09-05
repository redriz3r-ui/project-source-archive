import type { PresidentProfile } from "./PresidentProfiles";
import { Ink } from "./MagsaysayKit";

export type FigurePose =
  | "neutral"
  | "salute"
  | "point"
  | "welcome"
  | "listen"
  | "worried"
  | "sad";

export const PresidentFigure = ({
  profile,
  x,
  y,
  scale = 1,
  pose = "neutral",
}: {
  profile: PresidentProfile;
  x: number;
  y: number;
  scale?: number;
  pose?: FigurePose;
}) => {
  const left =
    pose === "salute"
      ? "M-8 -75 L-54 -128 L-20 -154"
      : pose === "point"
        ? "M-8 -76 L-82 -88 L-122 -112"
        : pose === "welcome"
          ? "M-8 -75 L-88 -115"
          : pose === "listen"
            ? "M-8 -75 L-55 -118 L-28 -153"
            : "M-8 -75 L-63 -20";
  const right =
    pose === "welcome"
      ? "M8 -75 L88 -115"
      : pose === "worried"
        ? "M8 -75 L53 -118 L27 -151"
        : "M8 -75 L62 -20";
  const hair =
    profile.hair === "bob"
      ? "M-43 -167 Q-25 -215 0 -207 Q35 -213 45 -165 L43 -123 L30 -140 Q42 -180 0 -188 Q-39 -181 -29 -139 L-43 -123 Z"
      : profile.hair === "receding"
        ? "M-33 -180 Q-8 -200 31 -178 Q12 -185 2 -176 Q-15 -187 -33 -174"
        : profile.hair === "short"
          ? "M-40 -174 Q-8 -207 39 -174 L34 -188 Q0 -213 -38 -187 Z"
          : profile.hair === "slick"
            ? "M-40 -173 Q-8 -210 42 -173 Q10 -193 -33 -172"
            : "M-38 -173 Q-10 -208 37 -176 Q12 -186 -27 -174";
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`}>
      <Ink>
        <circle cy="-158" r="43" fill={profile.skin} />
        <path d={hair} fill={profile.hairColor} />
        <path d="M-16 -151 l2 0 M16 -151 l2 0" strokeWidth="8" />
        {profile.glasses && (
          <>
            <circle cx="-17" cy="-151" r="13" />
            <circle cx="18" cy="-151" r="13" />
            <path d="M-4 -151 H5" />
          </>
        )}
        <path
          d={
            pose === "sad"
              ? "M-17 -133 Q0 -145 18 -132"
              : "M-18 -137 Q0 -122 20 -139"
          }
          strokeWidth="4"
        />
        <path d="M0 -113 V15" />
        <path d={left} />
        <path d={right} />
        <path d="M0 15 L-38 102 M0 15 L40 102" />
        <path
          d={
            profile.feminine
              ? "M-31 -105 Q0 -87 31 -105 L42 8 Q0 23 -42 8 Z"
              : "M-31 -105 Q0 -87 31 -105 L27 4 Q0 20 -27 4 Z"
          }
          fill={
            profile.outfit === "suit"
              ? "#53687a"
              : profile.outfit === "dress"
                ? profile.accent
                : "#fff1c8"
          }
        />
        <path d="M0 -92 V4" stroke={profile.accent} strokeWidth="3" />
      </Ink>
    </g>
  );
};
