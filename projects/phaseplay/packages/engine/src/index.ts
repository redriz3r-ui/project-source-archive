import { cents, type BankrollPlan, type Money, type Phase, type SessionPosture } from "@phaseplay/domain";

const SETTINGS: Record<SessionPosture, { protectedRate: number; stopRate: number; targetRate: number }> = {
  make_it_last: { protectedRate: 0.3, stopRate: 0.55, targetRate: 1.2 },
  balanced: { protectedRate: 0.25, stopRate: 0.5, targetRate: 1.25 },
  higher_variance: { protectedRate: 0.2, stopRate: 0.4, targetRate: 1.35 },
};

export function createBankrollPlan(startingBankroll: Money, posture: SessionPosture, requestedProtected?: Money): BankrollPlan {
  const settings = SETTINGS[posture];
  const protectedCash = requestedProtected ?? cents(Math.round(startingBankroll * settings.protectedRate));
  if (protectedCash >= startingBankroll) throw new Error("Protected cash must be less than the starting bankroll.");
  return {
    startingBankroll,
    protectedCash,
    playableBankroll: cents(startingBankroll - protectedCash),
    stopFloor: cents(Math.round(startingBankroll * settings.stopRate)),
    profitTarget: cents(Math.round(startingBankroll * settings.targetRate)),
    posture,
  };
}

export interface CoachingDecision {
  phase: Phase;
  action: "continue" | "reduce_risk" | "protect_profit" | "end_session";
  reason: string;
}

export function evaluateSession(plan: BankrollPlan, currentBalance: Money): CoachingDecision {
  if (currentBalance <= plan.stopFloor) return { phase: "stop", action: "end_session", reason: "Your preset stop floor has been reached." };
  if (plan.profitTarget && currentBalance >= plan.profitTarget) return { phase: "protect", action: "protect_profit", reason: "Your preset profit target has been reached." };
  const remainingPlayable = currentBalance - plan.protectedCash;
  if (remainingPlayable <= plan.playableBankroll * 0.25) return { phase: "protect", action: "reduce_risk", reason: "Only a quarter of the initial playable bankroll remains." };
  if (remainingPlayable <= plan.playableBankroll * 0.6) return { phase: "explore", action: "reduce_risk", reason: "Playable bankroll has moved below the session runway." };
  return { phase: "runway", action: "continue", reason: "The session remains within its preset runway." };
}
