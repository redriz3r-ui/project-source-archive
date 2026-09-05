import type { ReactNode } from "react";

export type MagsaysayPose =
  | "neutral"
  | "mechanic"
  | "salute"
  | "point"
  | "welcome"
  | "listen"
  | "worried"
  | "sad";
export const Ink = ({ children }: { children: ReactNode }) => (
  <g
    fill="none"
    stroke="#101820"
    strokeWidth="7"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    {children}
  </g>
);

export const Magsaysay = ({
  x,
  y,
  scale = 1,
  pose = "neutral",
  outfit = "barong",
}: {
  x: number;
  y: number;
  scale?: number;
  pose?: MagsaysayPose;
  outfit?: "barong" | "suit" | "mechanic";
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
              : "M-8 -75 L-63 -20",
    right =
      pose === "welcome"
        ? "M8 -75 L88 -115"
        : pose === "worried"
          ? "M8 -75 L53 -118 L27 -151"
          : "M8 -75 L62 -20";
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`}>
      <Ink>
        <circle cy="-158" r="43" fill="#d8a173" />
        <path
          d="M-38 -173 Q-10 -208 37 -176 Q12 -186 -27 -174"
          fill="#18212a"
        />
        <path d="M-16 -151 l2 0 M16 -151 l2 0" strokeWidth="8" />
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
        {outfit === "barong" && (
          <path
            d="M-31 -105 Q0 -87 31 -105 L27 4 Q0 20 -27 4 Z"
            fill="#fff1c8"
          />
        )}
        {outfit === "suit" && (
          <path
            d="M-34 -105 L0 -82 L34 -105 L28 7 L0 18 L-28 7 Z"
            fill="#53687a"
          />
        )}
        {outfit === "mechanic" && (
          <path d="M-34 -105 L34 -105 L27 7 L0 18 L-27 7 Z" fill="#477da4" />
        )}
        <path d="M0 -92 V4" stroke="#d49a13" strokeWidth="3" />
      </Ink>
      {pose === "mechanic" && <Wrench x={-78} y={-3} rotate={-28} />}
    </g>
  );
};
export const Citizen = ({
  x,
  y,
  color = "#db563d",
  hat = false,
  scale = 1,
}: {
  x: number;
  y: number;
  color?: string;
  hat?: boolean;
  scale?: number;
}) => (
  <g transform={`translate(${x} ${y}) scale(${scale})`}>
    <Ink>
      <circle cy="-112" r="29" fill="#d8a173" />
      {hat && (
        <path d="M-35 -124 Q0 -153 35 -124 M-50 -122 H50" fill="#c89b3c" />
      )}
      <path d="M0 -82 V4 M0 -58 L-38 -20 M0 -58 L39 -20 M0 4 L-24 63 M0 4 L25 63" />
      <path d="M-22 -75 Q0 -61 22 -75 L18 -2 Q0 9 -18 -2 Z" fill={color} />
    </Ink>
  </g>
);
export const Wrench = ({
  x,
  y,
  rotate = 0,
}: {
  x: number;
  y: number;
  rotate?: number;
}) => (
  <g transform={`translate(${x} ${y}) rotate(${rotate})`}>
    <Ink>
      <path d="M0 0 L0 -83 M-18 -105 Q0 -83 18 -105 M-7 2 A8 8 0 1 0 7 2" />
    </Ink>
  </g>
);
export const BallotBox = ({ x, y }: { x: number; y: number }) => (
  <g transform={`translate(${x} ${y})`}>
    <Ink>
      <rect x="-65" y="-45" width="130" height="110" rx="6" fill="#d9b26b" />
      <path d="M-77 -45 H77 L58 -78 H-58 Z" fill="#ead7a8" />
      <path d="M-25 -58 H25" />
    </Ink>
    <text
      x="0"
      y="25"
      textAnchor="middle"
      fontFamily="Arial"
      fontWeight="900"
      fontSize="20"
    >
      VOTE
    </text>
  </g>
);
export const LetterPile = ({ x, y }: { x: number; y: number }) => (
  <g transform={`translate(${x} ${y})`}>
    <Ink>
      {[0, 1, 2, 3].map((i) => (
        <g
          key={i}
          transform={`translate(${i * 12} ${-i * 22}) rotate(${i % 2 ? 3 : -3})`}
        >
          <rect x="-80" y="-45" width="160" height="90" fill="#fff" />
          <path d="M-80 -45 L0 12 L80 -45" />
        </g>
      ))}
    </Ink>
  </g>
);
export const Gate = ({
  x,
  y,
  open,
}: {
  x: number;
  y: number;
  open: number;
}) => (
  <g transform={`translate(${x} ${y})`}>
    <Ink>
      <g transform={`translate(${-95 * open} 0)`}>
        <rect x="-140" y="-150" width="140" height="180" />
        <path d="M-140 -100 H0 M-140 -45 H0 M-95 -150 V30 M-48 -150 V30" />
      </g>
      <g transform={`translate(${95 * open} 0)`}>
        <rect x="0" y="-150" width="140" height="180" />
        <path d="M0 -100 H140 M0 -45 H140 M48 -150 V30 M95 -150 V30" />
      </g>
    </Ink>
  </g>
);
export const TrustMeter = ({
  x,
  y,
  value,
}: {
  x: number;
  y: number;
  value: number;
}) => (
  <g transform={`translate(${x} ${y})`}>
    <Ink>
      <path d="M-105 55 A105 105 0 0 1 105 55" />
      <path
        d={`M0 55 L${Math.cos(Math.PI - Math.PI * value) * 92} ${55 - Math.sin(Math.PI - Math.PI * value) * 92}`}
        stroke="#d8322a"
        strokeWidth="11"
      />
    </Ink>
    <text
      x="0"
      y="92"
      textAnchor="middle"
      fontFamily="Arial"
      fontWeight="900"
      fontSize="23"
    >
      PUBLIC TRUST
    </text>
  </g>
);
export const Plane = ({
  x,
  y,
  rotate = 0,
}: {
  x: number;
  y: number;
  rotate?: number;
}) => (
  <g transform={`translate(${x} ${y}) rotate(${rotate})`}>
    <Ink>
      <path
        d="M-110 0 H110 L45 -18 L5 -80 H-22 L-5 -18 H-70 L-99 -48 H-118 L-105 0 L-118 48 H-99 L-70 18 H-5 L-22 80 H5 L45 18 Z"
        fill="#bbc6cb"
      />
    </Ink>
  </g>
);
