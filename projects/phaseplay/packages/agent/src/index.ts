import type { Session } from "@phaseplay/domain";
import { evaluateSession } from "@phaseplay/engine";

export interface CoachReply { message: string; decision: ReturnType<typeof evaluateSession>; }

export function buildCoachReply(session: Session): CoachReply {
  const decision = evaluateSession(session.plan, session.currentBalance);
  return {
    decision,
    message: `${decision.reason} This guidance manages your preset entertainment budget and does not predict gambling outcomes.`,
  };
}
