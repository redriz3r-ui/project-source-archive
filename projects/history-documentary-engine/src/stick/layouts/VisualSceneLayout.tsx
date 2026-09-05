import type { CSSProperties, ReactNode } from "react";

export type VisualSceneLayoutName =
  | "HERO_CENTER"
  | "EVIDENCE_LEFT"
  | "EVIDENCE_RIGHT"
  | "TWO_SIDED_CONTEXT"
  | "ENVIRONMENT_SCENE"
  | "EVIDENCE_TAKEOVER";

const photoBase: CSSProperties = {
  position: "absolute",
  overflow: "hidden",
  background: "#eee",
  boxShadow: "0 7px 18px #0003",
  border: "5px solid white",
};

export const VisualSceneLayout = ({
  layout,
  photo,
  art,
  progress,
}: {
  layout: VisualSceneLayoutName;
  photo: ReactNode;
  art: ReactNode;
  progress: number;
}) => {
  const drift = -1 + progress * 2;
  if (layout === "HERO_CENTER")
    return (
      <>
        <div
          style={{
            ...photoBase,
            left: 42,
            top: 155,
            width: 340,
            height: 420,
            transform: `rotate(${drift}deg)`,
          }}
        >
          {photo}
        </div>
        <div
          style={{
            position: "absolute",
            left: 330,
            top: 0,
            width: 620,
            height: 720,
          }}
        >
          {art}
        </div>
      </>
    );
  if (layout === "EVIDENCE_RIGHT")
    return (
      <>
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            width: 620,
            height: 720,
          }}
        >
          {art}
        </div>
        <div
          style={{
            ...photoBase,
            right: 30,
            top: 125,
            width: 620,
            height: 500,
            transform: `rotate(${-drift}deg)`,
          }}
        >
          {photo}
        </div>
      </>
    );
  if (layout === "TWO_SIDED_CONTEXT")
    return (
      <>
        <div
          style={{
            ...photoBase,
            left: 30,
            top: 145,
            width: 390,
            height: 430,
            transform: `rotate(${drift}deg)`,
          }}
        >
          {photo}
        </div>
        <div
          style={{
            position: "absolute",
            left: 330,
            top: 0,
            width: 620,
            height: 720,
          }}
        >
          {art}
        </div>
      </>
    );
  if (layout === "ENVIRONMENT_SCENE")
    return (
      <>
        <div
          style={{
            position: "absolute",
            left: 190,
            top: 0,
            width: 900,
            height: 720,
          }}
        >
          {art}
        </div>
        <div
          style={{
            ...photoBase,
            left: 32,
            top: 135,
            width: 330,
            height: 245,
            transform: `rotate(${drift}deg)`,
          }}
        >
          {photo}
        </div>
      </>
    );
  if (layout === "EVIDENCE_TAKEOVER")
    return (
      <>
        <div
          style={{
            ...photoBase,
            left: 28,
            top: 125,
            width: 790,
            height: 500,
            transform: `rotate(${drift}deg)`,
          }}
        >
          {photo}
        </div>
        <div
          style={{
            position: "absolute",
            right: -20,
            top: 35,
            width: 540,
            height: 650,
            background: "#fff",
            borderRadius: 26,
            boxShadow: "0 7px 22px #0003",
          }}
        >
          {art}
        </div>
      </>
    );
  return (
    <>
      <div
        style={{
          ...photoBase,
          left: 30,
          top: 125,
          width: 620,
          height: 500,
          transform: `rotate(${drift}deg)`,
        }}
      >
        {photo}
      </div>
      <div
        style={{
          position: "absolute",
          right: 0,
          top: 0,
          width: 620,
          height: 720,
        }}
      >
        {art}
      </div>
    </>
  );
};
